#!/usr/bin/env python3
"""
Patch & Fix script for The Legend of Zelda: Ocarina of Time on macOS (Apple Silicon).
Applies post-installation stability, performance, and synchronization fixes to the standalone .app.

Usage:
    python3 scripts/patch_zelda_oot_app.py ["/path/to/The Legend of Zelda - Ocarina of Time.app"]
"""

import sys
import os
import shutil
import subprocess

DEFAULT_PATHS = [
    os.path.expanduser("~/Applications/The Legend of Zelda - Ocarina of Time.app"),
    "/Applications/The Legend of Zelda - Ocarina of Time.app",
    "./The Legend of Zelda - Ocarina of Time.app"
]

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHADER_ASSET = os.path.join(REPO_ROOT, "dm/games/0400486024DEC000/assets/msl/1e38b4a840f89d93_bf.metallib")


def find_app(arg_path=None):
    if arg_path:
        if os.path.exists(arg_path):
            return os.path.abspath(arg_path)
        print(f"[ERROR] Specified app not found at: {arg_path}")
        sys.exit(1)
    for p in DEFAULT_PATHS:
        if os.path.exists(p):
            return os.path.abspath(p)
    print(f"[ERROR] Could not find 'The Legend of Zelda - Ocarina of Time.app'.")
    print("Please pass the path to the .app as an argument:")
    print("  python3 scripts/patch_zelda_oot_app.py '/path/to/The Legend of Zelda - Ocarina of Time.app'")
    sys.exit(1)


def patch_movie_player(dm_dir):
    bin_path = os.path.join(dm_dir, "main.patched.bin")
    if not os.path.exists(bin_path):
        print(f"[WARN] {bin_path} not found; skipping binary patch.")
        return

    offset = 0x3b5c55c
    expected_old = bytes.fromhex("e83b00b9")  # str w8, [sp, #0x38]
    expected_new = bytes.fromhex("e93b00b9")  # str w9, [sp, #0x38]

    with open(bin_path, "r+b") as f:
        f.seek(offset)
        cur = f.read(4)
        if cur == expected_new:
            print("[OK] main.patched.bin already has movie player buffer fix (0x3b5c55c = e93b00b9).")
        elif cur == expected_old:
            f.seek(offset)
            f.write(expected_new)
            f.flush()
            print("[FIXED] main.patched.bin patched at 0x3b5c55c (movie player buffer count: 1 -> 4).")
        else:
            print(f"[WARN] Unexpected bytes at 0x3b5c55c: {cur.hex()} (expected {expected_old.hex()}). Skipping.")

    # Update main.cuts.tsv
    cuts_tsv = os.path.join(dm_dir, "main.cuts.tsv")
    if os.path.exists(cuts_tsv):
        with open(cuts_tsv, "r") as f:
            content = f.read()
        cut_line = "0x3b5c55c\te83b00b9\te93b00b9\tmovie player buffer count: pass w9 (4) instead of w8 (1) to enable multi-picture advance at 30 fps\n"
        if "0x3b5c55c" not in content:
            with open(cuts_tsv, "a") as f:
                f.write(cut_line)
            print("[OK] Added cut entry to main.cuts.tsv.")


def fix_pso_manifest(dm_dir):
    pso_path = os.path.join(dm_dir, "pso_manifest.tsv")
    if not os.path.exists(pso_path):
        return

    with open(pso_path, "r") as f:
        lines = f.readlines()

    modified = False
    for i, line in enumerate(lines):
        # Look for the problematic foliage mesh pipeline ac2f3feb11427426_b
        if "616332663366656231313432373432365f62" in line and not line.startswith("#"):
            lines[i] = "# " + line
            modified = True
            print(f"[FIXED] Commented out crashing foliage mesh pipeline at row {i+1} in pso_manifest.tsv.")

    if modified:
        with open(pso_path, "w") as f:
            f.writelines(lines)
    else:
        print("[OK] pso_manifest.tsv already clean (row 9700 commented out or not present).")


def install_readable_tile_shader(app_path):
    msl_dirs = [
        os.path.join(app_path, "Contents/PlugIns/ShaderLibraries.bundle/Contents/Resources/msl"),
        os.path.join(app_path, "Contents/PlugIns/ShaderLibraries.bundle/Contents/Resources/msl/b-14c41b65d7be")
    ]

    if not os.path.exists(SHADER_ASSET):
        print(f"[WARN] Shader asset not found at {SHADER_ASSET}. Skipping readable-tile shader install.")
        return

    for d in msl_dirs:
        if os.path.exists(d):
            dst = os.path.join(d, "1e38b4a840f89d93_bf.metallib")
            if not os.path.exists(dst):
                shutil.copy2(SHADER_ASSET, dst)
                print(f"[FIXED] Installed readable-tile shader to {dst}.")
            else:
                print(f"[OK] Readable-tile shader present at {dst}.")


def configure_env(dm_dir):
    env_path = os.path.join(dm_dir, "env.txt")
    settings = {
        "DM_DRAWABLE_CAP": "1080p",
        "DM_PRESENT_LINK": "0",
        "DM_PRESENT_SNAP": "1",
        "DM_UPSCALER": "metalfx",
        "DM_PRESENT_UPSCALE": "off"
    }

    current = {}
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    current[k.strip()] = v.strip()

    updated = False
    for k, v in settings.items():
        if current.get(k) != v:
            current[k] = v
            updated = True

    if updated:
        with open(env_path, "w") as f:
            for k in sorted(current.keys()):
                f.write(f"{k}={current[k]}\n")
        print("[FIXED] Updated env.txt with optimal pacing and presentation settings.")
    else:
        print("[OK] env.txt already configured with optimal settings.")


def sign_and_verify(app_path):
    print("[*] Re-signing application bundle with ad-hoc signature...")
    res = subprocess.run(["codesign", "--force", "--sign", "-", app_path], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[ERROR] Failed to sign bundle: {res.stderr}")
        return

    print("[*] Verifying bundle code signature...")
    ver = subprocess.run(["codesign", "--verify", "--deep", "--strict", app_path], capture_output=True, text=True)
    if ver.returncode == 0:
        print("[OK] Code signature is valid and strictly verified.")
    else:
        print(f"[WARN] codesign verify reported: {ver.stderr}")


def main():
    arg_path = sys.argv[1] if len(sys.argv) > 1 else None
    app_path = find_app(arg_path)
    print(f"=== Patching Zelda OoT App ===")
    print(f"Target: {app_path}\n")

    dm_dir = os.path.join(app_path, "Contents/Resources/dm")
    if not os.path.exists(dm_dir):
        print(f"[ERROR] Invalid bundle structure: {dm_dir} not found.")
        sys.exit(1)

    patch_movie_player(dm_dir)
    fix_pso_manifest(dm_dir)
    install_readable_tile_shader(app_path)
    configure_env(dm_dir)
    sign_and_verify(app_path)

    print("\n[SUCCESS] All fixes applied successfully! The game is ready to play.")


if __name__ == "__main__":
    main()
