# LLM Context Report: Instagram HDR Converter

**Target Audience:** Future LLMs or developers taking over the project to understand why certain technical choices were made.

## Objective
To build a tool capable of generating ISO-compliant UltraHDR JPEGs that reliably trigger the HDR display feature in the Instagram mobile app.

## Architectural Findings & Deadends

### Deadend: Method 1 (Raw Decode via `libultrahdr` Dynamic Generation)
Our initial approach (Method 1) took a raw AVIF or TIFF HDR file and an SDR JPEG. It decoded the HDR into RAW P010 format, and used Google's `libultrahdr` to dynamically compute a gain map based on the difference between the SDR and HDR images.
- **The Issue:** `libultrahdr` generates dynamic HDR metadata (e.g., specific `GainMapMax` and `hdrCapacityMax` values) based on the image's mathematical properties. 
- **The Result:** Instagram's ingestion engine is extremely strict and rejected these files, stripping the HDR metadata upon upload. It appears Instagram prefers a very narrow range of metadata parameters or relies heavily on Adobe's exact output structures.

### Solution: Method 2 (Gain Map Injection/Assembly)
To circumvent Instagram's rejection, we reverse-engineered a known-working workflow (inspired by the shell scripts from user `karachungen`).
- **The Concept:** Instead of dynamically generating the gain map, we use Adobe Camera Raw to export an HDR JPEG containing a valid gain map. We then *extract* that gain map and forcefully stitch it onto a custom-edited SDR JPEG.
- **The Pipeline in `create_hdr_jpeg.py`**:
  1. Extract the `MPImage2` (Gain Map) from the Adobe HDR JPEG using `exiftool`.
  2. Strip *all* XMP metadata from both the SDR fallback image and the Gain Map image. (Duplicate or trailing XMP blocks cause Instagram to fail).
  3. Force both images into strict `4:2:0 YCbCr` subsampling using `ffmpeg`.
  4. Feed the images into `ultrahdr_app` using API-4 (`-m 0`), bypassing its computation engine entirely.
  5. Inject a static `hdr-config.cfg` file with known-working parameters (`maxContentBoost=16`, `hdrCapacityMax=16.5665`).
- **Result:** This structurally mirrors files that Instagram accepts, reliably triggering HDR.

## Known Limitations & Pitfalls
- **Mismatched Dimensions:** The single biggest point of failure in Method 2 is if the SDR image and the HDR image are exported with different pixel dimensions (e.g. one has a crop applied, the other doesn't). Because the script stitches the gain map from the HDR image directly over the SDR image, mismatched dimensions cause the highlight layer to squish or stretch.
- **Camera Raw Dependency:** The workflow absolutely requires the HDR input to be exported from Adobe Camera Raw (or Lightroom) so it contains the `MPImage2` gain map structure.

## Next Steps for Future LLMs
- Implement batch processing to handle directories of matched pairs (e.g., `image1_sdr.jpg` and `image1_hdr.jpg`).
- Implement an automated dimension-checking pre-flight function to abort or warn if the SDR and HDR inputs are not identically sized.
- Consider wrapping the CLI in a GUI tool using Gradio or Tkinter.
