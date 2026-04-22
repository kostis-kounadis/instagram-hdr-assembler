#!/usr/bin/env python3
"""
Instagram HDR Assembler
-----------------------
A robust 2-file CLI utility for generating Instagram-compliant HDR JPEGs.

This script takes two inputs:
  1. A custom-edited SDR fallback JPEG.
  2. An HDR exported file (JPEG, AVIF, TIFF) directly from Adobe Camera Raw.

IMPORTANT: For the guaranteed "Method 2" injection pipeline (which bypasses 
dynamic libultrahdr metadata generation), you must provide a Camera Raw 
HDR JPEG as your `--hdr` input. Both images must have the EXACT same pixel 
dimensions, otherwise the gain map highlight layer will stretch and misalign.

Dependencies:
  - libultrahdr (compiled with -DUHDR_WRITE_XMP=ON)
  - exiftool
  - ffmpeg
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import json

def get_dimensions(filepath, verbose=False):
    cmd = [
        'ffprobe', '-v', 'error', 
        '-select_streams', 'v:0', 
        '-show_entries', 'stream=width,height', 
        '-of', 'csv=s=x:p=0', 
        filepath
    ]
    if verbose:
        print(f"Running: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Failed to get dimensions from {filepath}. Error: {res.stderr}")
    
    out = res.stdout.strip()
    if out.endswith('x'):
        out = out[:-1]
    width, height = map(int, out.split('x'))
    return width, height

def main():
    parser = argparse.ArgumentParser(description="Create ISO HDR JPEG from AVIF/TIFF and SDR fallback")
    parser.add_argument("--sdr", required=True, help="Path to SDR JPEG (fallback image)")
    parser.add_argument("--hdr", required=True, help="Path to HDR source file (.avif or .tif/.tiff)")
    parser.add_argument("--output", required=True, help="Path for the output JPEG")
    parser.add_argument("--quality", type=int, default=95, help="JPEG quality 1-100 (default: 95)")
    parser.add_argument("--transfer", choices=['hlg', 'pq'], default='hlg', help="Transfer function: 'hlg' or 'pq' (default: 'hlg')")
    parser.add_argument("--sdr-gamut", choices=['bt709', 'p3', 'bt2100'], default='bt709', help="SDR color gamut (default: bt709)")
    parser.add_argument("--hdr-gamut", choices=['bt709', 'p3', 'bt2100'], default='p3', help="HDR color gamut (default: p3)")
    parser.add_argument("--verbose", action="store_true", help="Print detailed progress")
    
    args = parser.parse_args()
    
    # 1. PRE-FLIGHT VALIDATION
    if not os.path.exists(args.sdr):
        print(f"Error: SDR file not found: {args.sdr}")
        sys.exit(1)
    if not os.path.exists(args.hdr):
        print(f"Error: HDR file not found: {args.hdr}")
        sys.exit(1)
        
    with open(args.sdr, 'rb') as f:
        if f.read(2) != b'\xff\xd8':
            print(f"Error: SDR file is not a valid JPEG: {args.sdr}")
            sys.exit(1)
            
    local_path = os.path.join(os.path.dirname(__file__), '../libultrahdr/build/ultrahdr_app')
    if os.path.exists(local_path):
        ultrahdr_app = os.path.abspath(local_path)
    else:
        ultrahdr_app = shutil.which('ultrahdr_app')
        if not ultrahdr_app:
            print("Error: ultrahdr_app not found. Install libultrahdr: see Step 0.1 in the guide")
            sys.exit(1)
            
    ffmpeg_app = shutil.which('ffmpeg')
    if not ffmpeg_app:
        print("Error: ffmpeg not found in PATH")
        sys.exit(1)
            
    out_dir = os.path.dirname(os.path.abspath(args.output))
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
        
    sdr_abs = os.path.abspath(args.sdr)
    hdr_abs = os.path.abspath(args.hdr)
    out_abs = os.path.abspath(args.output)
    
    if args.verbose:
        print(f"SDR Input: {sdr_abs}")
        print(f"HDR Input: {hdr_abs}")
        print(f"Output: {out_abs}")
        
    # 2. HDR SOURCE HANDLING (Using ffmpeg as intermediate to p010le as diagnosed)
    try:
        width, height = get_dimensions(hdr_abs, args.verbose)
    except Exception as e:
        print(e)
        sys.exit(1)
    # 2. HDR SOURCE HANDLING
    if args.verbose:
        print(f"Detected HDR dimensions: {width}x{height}")
        
    # Branch logic based on HDR input format
    hdr_ext = hdr_abs.lower().split('.')[-1]
    
    if hdr_ext in ['jpg', 'jpeg']:
        # Method 2 Pipeline: Assemble using existing Gain Map
        print(f"Detected JPEG input. Using Method 2 Pipeline (API-4 Gain Map Injection)...")
        
        # Static Instagram configuration
        hdr_config = """--maxContentBoost 16
--minContentBoost 1
--gamma 1
--offsetSdr 1e-07
--offsetHdr 1e-07
--hdrCapacityMin 1
--hdrCapacityMax 16.5665
--useBaseColorSpace 1
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "hdr-config.cfg")
            with open(config_path, "w") as f:
                f.write(hdr_config)
                
            temp_gainmap = os.path.join(tmpdir, "temp_gainmap.jpg")
            temp_gainmap_420 = os.path.join(tmpdir, "gainmap_420.jpg")
            
            print("Extracting Gain Map from HDR source...")
            subprocess.run(['exiftool', '-b', '-MPImage2', hdr_abs], stdout=open(temp_gainmap, 'wb'), check=True)
            if not os.path.exists(temp_gainmap) or os.path.getsize(temp_gainmap) == 0:
                print("Error: No MPImage2 gain map found in the provided HDR JPEG.")
                sys.exit(1)
                
            print("Cleaning Gain Map XMP...")
            subprocess.run(['exiftool', '-xmp:all=', temp_gainmap, '-overwrite_original', '-q'], check=False)
            
            print("Converting Gain Map to 4:2:0 subsampling...")
            subprocess.run(['ffmpeg', '-y', '-i', temp_gainmap, '-pix_fmt', 'yuvj420p', '-q:v', '2', temp_gainmap_420], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            
            temp_sdr = os.path.join(tmpdir, "temp_sdr.jpg")
            temp_sdr_420 = os.path.join(tmpdir, "sdr_420.jpg")
            
            print("Cleaning SDR Fallback XMP...")
            shutil.copy2(sdr_abs, temp_sdr)
            subprocess.run(['exiftool', '-xmp:all=', temp_sdr, '-overwrite_original', '-q'], check=False)
            
            print("Converting SDR Fallback to 4:2:0 subsampling...")
            subprocess.run(['ffmpeg', '-y', '-i', temp_sdr, '-pix_fmt', 'yuvj420p', '-q:v', '2', temp_sdr_420], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                           
            print("Encoding final ISO UltraHDR JPEG (API-4)...")
            cmd = [
                ultrahdr_app,
                '-m', '0',
                '-i', temp_sdr_420,
                '-g', temp_gainmap_420,
                '-f', config_path,
                '-z', out_abs
            ]
            
            res_u = subprocess.run(cmd, capture_output=True, text=True)
            if res_u.returncode != 0:
                print(f"Error: ultrahdr_app conversion failed. stderr:\n{res_u.stderr}")
                sys.exit(1)
                
            if args.verbose:
                print("Method 2 Conversion successful. Validating output metadata...")
                
    else:
        # Method 1 Pipeline: AVIF/TIFF Decode to RAW P010
        # Strip XMP from SDR to prevent multiple XMP APP1 blocks
        sdr_clean = out_abs + "_sdr_clean.jpg"
        shutil.copy2(args.sdr, sdr_clean)
        subprocess.run([
            'exiftool', '-xmp:all=', '-overwrite_original', '-q', sdr_clean
        ], check=False)
        
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                # Decode HDR to P010 YUV
                yuv_path = os.path.join(tmpdir, "hdr.yuv")
                print("Decoding HDR input...")
                ffmpeg_cmd = [
                    'ffmpeg', '-y', '-i', args.hdr,
                    '-pix_fmt', 'p010le',
                    '-strict', '-1',
                    yuv_path
                ]
                subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # Determine width and height
                ffprobe_cmd = [
                    'ffprobe', '-v', 'error',
                    '-select_streams', 'v:0',
                    '-show_entries', 'stream=width,height',
                    '-of', 'csv=p=0',
                    args.hdr
                ]
                res = subprocess.run(ffprobe_cmd, capture_output=True, text=True, check=True)
                w, h = res.stdout.strip().strip(',').split(',')[:2]
                
                # Determine parameters
                t_val = '1' if args.transfer == 'hlg' else '2'
                gamut_map = {'bt709': '0', 'p3': '1', 'bt2100': '2'}
                c_val = gamut_map[args.sdr_gamut]
                C_val = gamut_map[args.hdr_gamut]
                
                print("Encoding ISO UltraHDR JPEG...")
                cmd = [
                    ultrahdr_app,
                    '-m', '0',
                    '-p', yuv_path,
                    '-w', w,
                    '-h', h,
                    '-i', sdr_clean,
                    '-a', '0',
                    '-t', t_val,
                    '-c', c_val,
                    '-C', C_val,
                    '-M', '0',
                    '-q', str(args.quality),
                    '-z', out_abs
                ]
                
                if args.verbose:
                    print(f"Running encoding command...")
                    print(f"Command: {' '.join(cmd)}")
                res_u = subprocess.run(cmd, capture_output=True, text=True)
                if res_u.returncode != 0:
                    print(f"Error: ultrahdr_app conversion failed. stderr:\n{res_u.stderr}")
                    sys.exit(1)
                    
                if args.verbose:
                    print("Conversion successful. Validating output metadata...")
                    
        finally:
            if os.path.exists(sdr_clean):
                os.remove(sdr_clean)
            
    # 4. POST-CONVERSION VALIDATION
    tf_mp2 = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
    temp_mp2 = tf_mp2.name
    tf_mp2.close()
    
    try:
        res_ex1 = subprocess.run(['exiftool', '-b', '-MPImage2', out_abs], capture_output=True)
        if res_ex1.returncode == 0 and res_ex1.stdout:
            with open(temp_mp2, 'wb') as f:
                f.write(res_ex1.stdout)
                
            res_ex2 = subprocess.run(['exiftool', '-j', '-G1', '-hdrgm:all', temp_mp2], capture_output=True, text=True)
            if res_ex2.returncode == 0:
                try:
                    data = json.loads(res_ex2.stdout)
                    if len(data) > 0:
                        metadata = data[0]
                        print("\n--- Validation Report ---")
                        for k, v in metadata.items():
                            if 'hdrgm' in k.lower() or 'gainmap' in k.lower():
                                print(f"{k}: {v}")
                                
                        version = metadata.get('XMP-hdrgm:Version')
                        gmin = metadata.get('XMP-hdrgm:GainMapMin')
                        gmax = metadata.get('XMP-hdrgm:GainMapMax')
                        hcmax = metadata.get('XMP-hdrgm:HDRCapacityMax')
                        
                        if gmin is not None and float(gmin) < 0:
                            print("\nWARNING: GainMapMin is negative. Instagram may reject this file. Try adjusting HDR export settings in Camera Raw.")
                            
                except json.JSONDecodeError:
                    pass
    finally:
        if os.path.exists(temp_mp2):
            os.remove(temp_mp2)
            
    print(f"\nDone! HDR JPEG created at: {out_abs}")

if __name__ == "__main__":
    main()
