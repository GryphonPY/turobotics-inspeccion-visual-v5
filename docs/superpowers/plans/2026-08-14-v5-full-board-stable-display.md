# V5 Full Board Stable Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore V4-style full-sheet presentation in V5 while preventing homography jitter from keeping the live workflow in `ESTABILIZANDO`.

**Architecture:** `BoardTracker` will produce both a canonical full-board image and the existing 8 × 14 cm ROI. The ROI remains the analyzer input; the canonical board becomes the public display. Small valid homography changes are held so the ROI and presence measurement do not jump between frames.

**Tech Stack:** Python 3.11, OpenCV ArUco, NumPy, PySide6, pytest, Ruff.

## Global Constraints

- V4 source and data remain untouched.
- Existing reference files, C01–C10 definitions, and camera calibration are reused.
- The system remains CPU-only and offline.
- Color is not used as a quality rule.
- The existing raw-camera fallback remains visible when the board is not detected.

---

### Task 1: Add a stable full-board observation contract

**Files:**
- Modify: `src/inspection_v5/contracts.py`
- Modify: `src/inspection_v5/board_tracker.py`
- Modify: `config/v5/runtime.json`
- Test: `tests_v5/test_board_tracker.py`

**Interfaces:**
- `TrackingSnapshot.board: np.ndarray | None` is the canonical 1728 × 2235 BGR board image when a valid homography exists.
- `BoardTracker.roi_bbox_to_board(bbox)` converts an analyzer ROI bounding box into canonical-board coordinates.

- [ ] **Step 1: Write failing tests for board output and stable transform hold**

Add these assertions to `tests_v5/test_board_tracker.py`:

```python
def test_tracker_returns_full_canonical_board_and_roi() -> None:
    config = V5BoardConfig.from_json(ROOT / "config" / "v5" / "runtime.json")
    observation = BoardTracker(config).observe(packet(synthetic_board()), now=1.0)

    assert observation.board is not None
    assert observation.board.shape[:2] == (2235, 1728)
    assert observation.roi is not None
    assert observation.roi.shape[:2] == (560, 320)


def test_tracker_holds_small_homography_jitter() -> None:
    config = V5BoardConfig.from_json(ROOT / "config" / "v5" / "runtime.json")
    tracker = BoardTracker(config)
    source = synthetic_board()
    first = tracker.observe(packet(source, 1), now=1.0)
    shifted = cv2.warpAffine(source, np.float32([[1, 0, 0.6], [0, 1, 0.4]]), source.shape[1::-1])
    second = tracker.observe(packet(shifted, 2), now=1.1)

    assert first.board is not None and second.board is not None
    assert float(np.mean(cv2.absdiff(first.board, second.board))) < 2.0


def test_tracker_converts_roi_bbox_to_board_coordinates() -> None:
    config = V5BoardConfig.from_json(ROOT / "config" / "v5" / "runtime.json")
    board_bbox = BoardTracker(config).roi_bbox_to_board((10, 20, 100, 200))

    assert board_bbox == (564, 598, 200, 400)
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests_v5\test_board_tracker.py -q
```

Expected: failure because `TrackingSnapshot.board` and `roi_bbox_to_board` do not exist and the tracker currently warps only the ROI.

- [ ] **Step 3: Add the board field and stabilization configuration**

Add `board` as a defaulted field at the end of `TrackingSnapshot` so existing positional constructors remain compatible:

```python
board: np.ndarray | None = None
```

Add this board setting to `config/v5/runtime.json`:

```json
"homography_hold_px": 2.0
```

Load it in `V5BoardConfig` as `homography_hold_px: float`.

- [ ] **Step 4: Implement one canonical warp plus a physical ROI crop**

In `BoardTracker.observe`, after a valid or cached homography is selected:

```python
board = cv2.warpPerspective(frame, homography, self.config.canonical_size_px)
roi_x = round(self.config.roi_mm["x"] * self.config.pixels_per_mm)
roi_y = round(self.config.roi_mm["y"] * self.config.pixels_per_mm)
roi_w = round(self.config.roi_mm["width"] * self.config.pixels_per_mm)
roi_h = round(self.config.roi_mm["height"] * self.config.pixels_per_mm)
roi_board = board[roi_y : roi_y + roi_h, roi_x : roi_x + roi_w]
roi = cv2.resize(roi_board, self.config.roi_output_px, interpolation=cv2.INTER_AREA)
```

Return `board=board` and `roi=roi` in the snapshot. Keep one `warpPerspective` call per observation.

- [ ] **Step 5: Hold only small valid homography changes**

Compare the four projected source-frame corners from the current candidate and the last accepted homography. If their mean displacement is at most `homography_hold_px`, keep the last accepted transform; if it is larger, accept the new candidate. Do not hold an invalid candidate or a candidate with reprojection error above the existing limit.

Implement the conversion used by the public overlay:

```python
def roi_bbox_to_board(self, bbox: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x, y, width, height = bbox
    scale_x = self.config.roi_mm["width"] * self.config.pixels_per_mm / self.config.roi_output_px[0]
    scale_y = self.config.roi_mm["height"] * self.config.pixels_per_mm / self.config.roi_output_px[1]
    origin_x = self.config.roi_mm["x"] * self.config.pixels_per_mm
    origin_y = self.config.roi_mm["y"] * self.config.pixels_per_mm
    return (round(origin_x + x * scale_x), round(origin_y + y * scale_y), round(width * scale_x), round(height * scale_y))
```

- [ ] **Step 6: Run the focused tests and verify they pass**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests_v5\test_board_tracker.py -q
```

Expected: all focused tracker tests pass and the tracker still performs exactly one perspective warp.

### Task 2: Publish the full board without changing the analyzer input

**Files:**
- Modify: `src/inspection_v5/runtime.py`
- Test: `tests_v5/test_runtime.py`

**Interfaces:**
- `_publish_public(tracked, full_frame=None)` selects `tracked.board` first, then the raw camera frame if the board is unavailable.
- `PublicState.frame` is the display image only; `TrackingSnapshot.roi` remains the inspector image.

- [ ] **Step 1: Write a failing runtime display test**

Add:

```python
def test_runtime_prefers_full_board_for_public_display() -> None:
    runtime = InspectionRuntime(ROOT)
    board = np.full((2235, 1728, 3), 18, dtype=np.uint8)
    roi = np.full((560, 320, 3), 220, dtype=np.uint8)
    runtime._publish_public(
        TrackingSnapshot(1, 1.0, True, roi, (0, 0, 0, 0), 0.0, 0.0, 0.0, board=board),
        np.zeros((1080, 1920, 3), dtype=np.uint8),
    )

    displayed = runtime.latest_public_state().frame

    assert displayed is not None
    assert displayed.shape[:2] == (2235, 1728)
    assert int(displayed[0, 0, 0]) == 18
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests_v5\test_runtime.py -q
```

Expected: failure because the runtime currently publishes the ROI instead of the full board.

- [ ] **Step 3: Use board-first display selection and convert the overlay box**

Replace the display selection in `_publish_public` with:

```python
display_frame = tracked.board if tracked.board is not None else full_frame
display_bbox = self.tracker.roi_bbox_to_board(tracked.bbox) if tracked.board is not None else (0, 0, 0, 0)
```

Use `display_frame` for `PublicState.frame` and `display_bbox` for `PublicState.tracking_bbox`. Keep the raw fallback when `tracked.board` is `None`.

- [ ] **Step 4: Run runtime tests and verify they pass**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests_v5\test_runtime.py -q
```

Expected: all runtime tests pass, including raw-frame fallback and board-first display.

### Task 3: Reduce false movement from capture noise

**Files:**
- Modify: `src/inspection_v5/presence.py`
- Modify: `src/inspection_v5/live_state.py`
- Test: `tests_v5/test_presence.py`
- Test: `tests_v5/test_live_state.py`

**Interfaces:**
- Segmentation keeps the existing grayscale threshold and color-independent behavior.
- Motion comparison uses a 3 × 3 Gaussian-smoothed grayscale frame and a three-sample median in the live controller.

- [ ] **Step 1: Write failing noise-tolerance tests**

Add these deterministic tests to `tests_v5/test_presence.py` and `tests_v5/test_live_state.py`:

```python
def test_motion_ignores_high_frequency_sensor_noise() -> None:
    analyzer = PresenceAnalyzer()
    previous = np.full((120, 120), 30, dtype=np.uint8)
    checker = np.indices(previous.shape).sum(axis=0) % 2
    current = np.where(checker == 0, 28, 32).astype(np.uint8)

    measured = analyzer.measure(current, previous)

    assert measured.motion < 1.0
```

```python
def test_isolated_motion_spike_does_not_reset_stability() -> None:
    controller = LiveController(LiveConfig(stability_seconds=0.35))
    feed(controller, occupied=0.50, motion=0.0, at=0.00)
    feed(controller, occupied=0.50, motion=0.0, at=0.10)
    feed(controller, occupied=0.50, motion=3.0, at=0.20)
    feed(controller, occupied=0.50, motion=0.0, at=0.30)
    event = feed(controller, occupied=0.50, motion=0.0, at=0.50)

    assert event.start_inspection
```

- [ ] **Step 2: Run the focused tests and verify the new tests fail**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests_v5\test_presence.py tests_v5\test_live_state.py -q
```

Expected: the new noise tests fail before smoothing and history are implemented.

- [ ] **Step 3: Smooth only the motion signal and keep segmentation unchanged**

In `PresenceAnalyzer.measure`, calculate `motion_gray` and `previous_motion_gray` with `cv2.GaussianBlur(gray, (3, 3), 0)` before `absdiff`; leave the threshold, mask, contour, area, and focus calculations on the existing grayscale image.

In `LiveController`, keep a `deque[float]` with `maxlen=3`, clear it when the board is unavailable or the area becomes empty, and calculate `stable` from the median of the history. This prevents one driver spike from resetting the 500 ms stability window.

- [ ] **Step 4: Run focused tests and verify they pass**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests_v5\test_presence.py tests_v5\test_live_state.py -q
```

Expected: all presence and live-state tests pass without changing color-invariance tests.

### Task 4: Make the stability message fit the screen

**Files:**
- Modify: `src/inspection_v5/ui/result_panel.py`
- Modify: `src/inspection_v5/ui/theme.py`
- Modify: `src/inspection_v5/ui/video_view.py`
- Test: `tests_v5/ui/test_widgets.py`

**Interfaces:**
- The user-visible headline remains exactly `ESTABILIZANDO`.
- The map, counters, and semantic colors remain unchanged.

- [ ] **Step 1: Write a UI regression test**

Add this test to `tests_v5/ui/test_widgets.py`:

```python
def test_stabilizing_headline_fits_result_panel(qtbot) -> None:
    panel = ResultPanel()
    qtbot.addWidget(panel)
    panel.resize(420, 700)
    panel.apply(PresentationViewModel.from_public_state(PublicState(tracking_mode=TrackingMode.STABILIZING)))
    panel.show()
    qtbot.wait(20)

    assert panel.headline.text() == "ESTABILIZANDO"
    assert not panel.headline.wordWrap()
    assert panel.headline.sizeHint().width() <= panel.headline.width()
```

- [ ] **Step 2: Run the UI test and verify it fails or captures the current layout**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests_v5\ui\test_widgets.py -q
```

- [ ] **Step 3: Reduce headline size and keep the video overlay inside its image**

Change the headline style from 49 px to 42 px, set `self.headline.setWordWrap(False)`, and give it a minimum height. In `TrackingVideoView.paintEvent`, clamp the overlay label rectangle so its top is at least 6 px inside the video widget.

- [ ] **Step 4: Run UI tests and render the review images**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests_v5\ui -q
.venv\Scripts\python.exe tools\render_v5_ui.py
```

Expected: the full sheet is visible, the central inspection rectangle remains present in the image, and `ESTABILIZANDO` is not clipped.

### Task 5: Full validation and delivery

**Files:**
- Verify only; no additional source changes expected.

- [ ] **Step 1: Run the complete test suite**

```powershell
.venv\Scripts\python.exe -m pytest tests tests_v5 -q
```

Expected: all tests pass; deprecation warnings from the existing ONNX exporter may remain.

- [ ] **Step 2: Run lint and protected-file verification**

```powershell
.venv\Scripts\python.exe -m ruff check src tests tests_v5 tools --exclude tools\package_v5.ps1
.venv\Scripts\python.exe tools\v5_snapshot.py verify
git diff --check
```

Expected: Ruff passes, protected V4 files are unchanged, and Git reports no whitespace errors.

- [ ] **Step 3: Commit the implementation**

```powershell
git add -- src/inspection_v5/contracts.py src/inspection_v5/board_tracker.py src/inspection_v5/runtime.py src/inspection_v5/presence.py src/inspection_v5/live_state.py src/inspection_v5/ui/result_panel.py src/inspection_v5/ui/theme.py src/inspection_v5/ui/video_view.py config/v5/runtime.json tests_v5/test_board_tracker.py tests_v5/test_runtime.py tests_v5/test_presence.py tests_v5/test_live_state.py tests_v5/ui/test_widgets.py
git commit -m "fix(v5): stabilize full-board live view"
```
