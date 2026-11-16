# The Legend of Zelda: Ocarina of Time (Switch 2) on macOS Apple Silicon

Complete standalone build guide, stability & performance fixes, and single-prompt AI replication instructions for running *The Legend of Zelda: Ocarina of Time* (`0400486024DEC000`, v131072) natively on Apple Silicon (M1/M2/M3/M4) via `nxnative`.

---

## ⚡ 1. Single-Prompt AI Replication

### Option A: Clean Build from Scratch
If building from scratch using your `.nup` container, paste this prompt into your AI assistant:

```markdown
Please build a self-contained, standalone macOS application for The Legend of Zelda: Ocarina of Time using the patched nxnative repository:

1. Clone https://github.com/lcguinea/nxnative.git into ./nxnative and work inside it.
2. Local game container:
   - Path: "/path/to/The Legend of Zelda Ocarina of Time [0400486024dec000][v131072].nup"
3. Execution steps:
   - Unpack the container and rewrite modules with the 0400486024DEC000 profile.
   - Verify that the movie player buffer cut in dm/games/0400486024DEC000/patches.py (0x3b5c55c e83b00b9 -> e93b00b9) is applied to main.patched.bin to ensure 60 fps AV1 cutscene audio/video sync.
   - Compile all shaders with PR #1359 float atomics (DMSH_CHAIN 14c41b65d7be).
   - Build dmhost with memory release optimizations (PRs #1455, #1447, #1394, #1439).
   - Package the standalone .app to ~/Applications with the 720p romfs_overlay and 1080p MetalFX upscaler.
   - Run: python3 scripts/patch_zelda_oot_app.py "~/Applications/The Legend of Zelda - Ocarina of Time.app"
   - Verify code signing: codesign --verify --deep --strict "~/Applications/The Legend of Zelda - Ocarina of Time.app"
```

### Option B: Fix an Already-Installed Game
If you already built or installed the game previously (using the original unpatched guide or repository) and are experiencing crashes, shader prewarm errors, lag, or out-of-sync cutscenes, paste this prompt into your AI assistant:

```markdown
I already installed "The Legend of Zelda - Ocarina of Time.app" on macOS Apple Silicon, but it has stability, performance, and cutscene audio/video desync bugs. Please fix all bugs using the patched nxnative repository:

1. Clone https://github.com/lcguinea/nxnative.git into ./nxnative (or pull latest main).
2. Locate the existing application (e.g. "~/Applications/The Legend of Zelda - Ocarina of Time.app" or "/Applications/The Legend of Zelda - Ocarina of Time.app").
3. Apply all fixes:
   - Inside nxnative, build the patched dmhost binary (ninja -C dm/host/gen/0400486024DEC000 dmhost) to fix the MTL4MeshRenderPipelineDescriptor crash and add DM_DRAWABLE_CAP 1080p scaling, and update Contents/MacOS/dmhost.
   - Run: python3 scripts/patch_zelda_oot_app.py "/path/to/The Legend of Zelda - Ocarina of Time.app"
     This automatically:
     - Patches main.patched.bin at 0x3b5c55c (e83b00b9 -> e93b00b9) to fix the 60 fps AV1 intro cutscene audio/dialog/video desync.
     - Comments out line 9700 in pso_manifest.tsv (prevents Apple LLVM XPC compiler crash during shader prewarm).
     - Installs the readable-tile shader 1e38b4a840f89d93_bf.metallib.
     - Configures optimal settings in env.txt (DM_DRAWABLE_CAP=1080p, DM_PRESENT_LINK=0, DM_PRESENT_SNAP=1, DM_UPSCALER=metalfx).
     - Re-signs the bundle with ad-hoc signature and verifies strictly.
4. Launch the application and verify that the intro cutscene, dialogs, and audio play in perfect 1:1 synchronization.
```

---

## 🛠️ 2. One-Command Fix for Existing Builds

If you already have a built `/Applications/The Legend of Zelda - Ocarina of Time.app` that suffers from crashes, lag, or out-of-sync cutscenes, run:

```bash
git clone https://github.com/lcguinea/nxnative.git
cd nxnative
python3 scripts/patch_zelda_oot_app.py "/Applications/The Legend of Zelda - Ocarina of Time.app"
```

The script automatically:
1. Unlocks up to 2-picture advance per frame in `main.patched.bin` at `0x3b5c55c` (fixes the intro cutscene audio/video desync).
2. Comments out the crashing foliage mesh pipeline (row 9700) in `pso_manifest.tsv`.
3. Installs the missing readable-tile shader `1e38b4a840f89d93_bf.metallib`.
4. Optimizes `env.txt` (`DM_DRAWABLE_CAP=1080p`, `DM_PRESENT_LINK=0`, `DM_PRESENT_SNAP=1`, `DM_UPSCALER=metalfx`).
5. Re-signs the bundle with ad-hoc signature and verifies integrity.

---

## 🔍 3. Fixes Breakdown & Technical Root Causes

### 1. Intro Cutscene Audio/Video/Dialog Desynchronization
- **Symptom**: In the opening sequence, the 60 fps AV1 intro cutscene played in half-speed slow motion (taking 20s to play 10s of video), while background music (`audren`) and dialog boxes advanced at normal speed, causing total desynchronization.
- **Root Cause**: In `main.patched.bin` at `0x3b5c55c`, the player constructor hardcoded `str w8, [sp, #0x38]` where `w8 = 1`. This clamped `[x19, #0x20] = 1` (max pictures to advance per tick) and allocated only 2 decoder buffers. At 30 fps (hold 2 vsyncs), the accumulator computed `floor(2.0 / 1.0) = 2`, but was clamped to 1 picture per frame.
- **Fix**: Changed `0x3b5c55c` to `str w9, [sp, #0x38]` (`e83b00b9` -> `e93b00b9`), passing `w9 = 4`. This allocates 4 buffers and allows advancing 2 pictures per frame at 30 fps, keeping video at exact 60 pictures/s in 1:1 real-time sync with audio and dialogs.

### 2. Mesh Pipeline Startup Assertion Crash
- **Symptom**: Application crashed immediately on launch with:
  `validateWithDevice: failed assertion: vertexFunction must not be nil (CRASH sig=6)`.
- **Root Cause**: `arch_lookup` and `arch_harvest` in `dm/gfx/nvn/nvn_mtl.m` passed mesh pipeline descriptors (`MTL4MeshRenderPipelineDescriptor`) to `MTL4Archive`, which requires a standard vertex function on non-mesh descriptors.
- **Fix**: Guarded `arch_lookup` and `arch_harvest` against `[d isKindOfClass:MTL4MeshRenderPipelineDescriptor.class]`.

### 3. Apple LLVM Compiler Crash During Shader Prewarm
- **Symptom**: Prewarming crashed with `XPC_ERROR_CONNECTION_INTERRUPTED` caused by a memory fault in Apple LLVM (`llvm::MachineOperand::setReg`) when compiling foliage mesh shader `ac2f3feb11427426_b`.
- **Root Cause**: Apple's Metal compiler service fails on certain complex mesh shader register allocations in that specific pipeline.
- **Fix**: Commented out row 9700 in `dm/games/0400486024DEC000/pso_manifest.tsv`. All remaining 163 mesh pipelines and 2,691 render pipelines now prewarm cleanly in ~4 seconds.

### 4. Missing Readable-Tile Shader
- **Symptom**: `[RED] failed to load the readable-tile version .../1e38b4a840f89d93_bf.metallib`.
- **Fix**: Compiled `1e38b4a840f89d93_bf.metallib` from MSL (`main0_f`) and included it in `dm/games/0400486024DEC000/assets/msl/`.

### 5. High-DPI Retina GPU Overload & Background Pacing Stalls
- **Symptom**: Severe frame drops (down to 20 fps / 50 ms per frame) on Retina displays (e.g. 3024x1964 or 4K/5K screens) and display link stalls when window focus shifted.
- **Fix**:
  - Implemented `DM_DRAWABLE_CAP` in `dm/host/front_mac.m` (`fitDrawable`), capping backing scale to 1080p (1920x1080).
  - Configured `DM_PRESENT_LINK=0` in `env.txt` to eliminate background display link pacing stalls.

---

## 🎮 4. Keyboard & Gamepad Controls

### Keyboard Layout
| Key | Switch Controller | In-Game Action |
| :--- | :--- | :--- |
| <kbd>W</kbd> <kbd>A</kbd> <kbd>S</kbd> <kbd>D</kbd> | **Left Stick** | Walk / Run / Swim |
| <kbd>J</kbd> | **A** | Action / Roll / Talk / Check / Confirm |
| <kbd>K</kbd> | **B** | Sword Attack / Cancel |
| <kbd>U</kbd> | **X** | Equipped Item (X) |
| <kbd>I</kbd> | **Y** | Equipped Item (Y) |
| <kbd>Z</kbd> | **ZL** | **Z-Targeting** (Lock-on camera / Shield) |
| <kbd>C</kbd> | **ZR** | Equipped Item / Action (ZR) |
| <kbd>E</kbd> | **R** | Use Shield (Guard) |
| <kbd>Q</kbd> | **L** | L Button |
| <kbd>Return</kbd> | **+ (Plus)** | Pause / Inventory & Gear Subscreens |
| <kbd>Tab</kbd> | **− (Minus)** | Map Subscreen |
| <kbd>←</kbd> <kbd>↑</kbd> <kbd>→</kbd> <kbd>↓</kbd> | **D-Pad** | Quick Items / D-Pad |
| <kbd>Shift</kbd> + <kbd>Arrow Keys</kbd> | **Right Stick** | Free Camera Rotation |
| <kbd>Space</kbd> | **Motion Shake** | Controller Shake |

*Controllers (Switch Pro, Joy-Cons, DualSense, Xbox) are automatically detected over Bluetooth or USB.*
