# Instagram HDR Assembler

A python-based CLI utility for generating ISO-compliant UltraHDR JPEGs, that trigger the HDR display feature in the Instagram app.

## 1. Context

### What does this app do?
Instagram's support for HDR images is notoriously fickle. HDR files exported from Camera Raw or Lightroom often lose their HDR metadata upon upload. This project acts as an **assembler**. 

It takes two images—a custom-edited SDR image and an HDR image exported from Adobe Camera Raw—and mathematically stitches them together. It injects a static, known-working metadata configuration that forces Instagram's ingestion engine to recognize and display the image in HDR.

### How it works (and limitations)
The utility requires two inputs: an SDR fallback image and an HDR image, both exported from Adobe Camera Raw. It then **extracts** the existing gain map from the HDR export, cleanses the files of any conflicting or duplicate XMP metadata, enforces compliance with Instagram's strict UltraHDR requirements, and packages them back together into a single JPG file.
* **Limitation:** This workflow relies on a Adobe Camera Raw (or Lightroom) workflow. 
* **Limitation:** Both your input images (the SDR and the HDR) **MUST** have the exact same pixel dimensions. If they do not, the highlight layer will stretch and you will get rather experimental (sometimes quite interesting!) results. 🙂

## 2. The Landscape (Why this exists)
There are a few ways to get HDR photos onto Instagram, each with their own pros and cons:

* **[WSP Plugin](https://gregbenzphotography.com/wsp/)**: A highly refined, commercial plugin for Photoshop. It provides excellent functionality and ease of use, but is a paid product.
* **[Instagram HDR Converter](https://github.com/karachungen/Instagram-HDR-Converter)**: An excellent, open-source bash implementation. Its reliance on a single-file input is a massive plus for speed and simplicity. However, there have been cases that Method 1 does not work and Method 2 produces weird results.
* **This Project (Instagram HDR Assembler)**: We trade a bit of simplicity for maximum control. By utilizing a **two-file workflow**, this tool requires a bit more effort from the user (exporting two separate files), but gives you absolute creative freedom over your SDR fallback while remaining 100% free and open-source.

## 3. Installation & Dependencies

This script relies on three core dependencies:

1. **exiftool**: Used for extracting and cleaning metadata.
   * `brew install exiftool` (macOS)
2. **ffmpeg**: Used for enforcing 4:2:0 YCbCr subsampling.
   * `brew install ffmpeg` (macOS)
3. **libultrahdr (Custom Compilation)**: Google's library for encoding UltraHDR JPEGs. 
   * **Crucial:** You cannot use a pre-compiled version. You must compile it locally with XMP writing enabled.

### Compiling `libultrahdr`
Run these commands in your terminal to clone and build the library:
```bash
git clone https://github.com/google/libultrahdr.git
cd libultrahdr
mkdir build && cd build
cmake -G "Unix Makefiles" -DUHDR_WRITE_XMP=ON ../
make
```
Ensure the `libultrahdr` folder is located in the same root directory as this project, or the script will not be able to locate the `ultrahdr_app` executable.

## 4. How to Use

Because this pipeline relies on a two-file system, your export process from Adobe Camera Raw (or Lightroom) is the most important step.

### Export Settings Template

| Parameter | SDR Export | HDR Export |
| :--- | :--- | :--- |
| **File type** | JPG | JPG (not AVIF or JXL) |
| **Color Space** | sRGB | HDR (e.g. Display P3 or Rec. 2020) |
| **Compatibility** | OFF | OFF |
| **Dimensions** | Instagram supported (i.e., 1080x1080, 1080x566 landscape, 1920x1080 portrait) | **MUST MATCH SDR EXACTLY** |

### Running the Script

Once you have your two files, run the python script via CLI:

```bash
python3 scripts/create_hdr_jpeg.py \
  --sdr path/to/your/SDR_file.jpg \
  --hdr path/to/your/HDR_file.jpg \
  --output final_instagram_upload.jpg
```

**What the script does automatically:**
1. Extracts the gain map from your HDR input.
2. Cleans both the SDR and Gain Map of conflicting metadata.
3. Subsamples both layers to 4:2:0.
4. Assembles them using API-4 injection and the required Instagram configuration parameters.

### Upload to Instagram via Desktop

Upload the resulting `final_instagram_upload.jpg` to Instagram from your Desktop device using "Original" option in Instagram's upload settings!

## Future
- Implement batch processing to handle directories of matched pairs (e.g., `image1_sdr.jpg` and `image1_hdr.jpg`).
- Implement an automated dimension-checking pre-flight function to abort or warn if the SDR and HDR inputs are not identically sized or if they are not the specific instagram supported sizes. 
- Consider wrapping the CLI in a GUI tool (droplet, webapp, etc).
- Investigate using the [Pure Rust Ultra HDR (gain map HDR) encoder/decoder](https://github.com/imazen/ultrahdr) as a more efficient replacement for libultrahdr.

## Acknowledgements & Disclaimer

**Disclaimer**: This project and its underlying logic were heavily scaffolded and generated by Artificial Intelligence, followed by rigorous human testing and iteration to verify compatibility against Instagram's opaque ingestion filters.

**Acknowledgements**:
* **[Karachungen](https://github.com/karachungen)** for the structural groundwork on manipulating the `MPImage2` gain map and the specific API-4 injection configuration needed to bypass Instagram's filters.
* **[Google](https://github.com/google/libultrahdr)** for the core `libultrahdr` project which makes ISO 21496-1 manipulation possible.
