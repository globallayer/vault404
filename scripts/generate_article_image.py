"""
Generate article image for vault404 Medium article using fal.ai

Usage:
    FAL_KEY=your_api_key python generate_article_image.py

Or set FAL_KEY environment variable first.
"""

import os
import sys
import fal_client

def main():
    # Check for API key
    if not os.environ.get("FAL_KEY"):
        print("ERROR: FAL_KEY environment variable not set")
        print("\nTo get a key:")
        print("1. Go to https://fal.ai")
        print("2. Sign up / log in")
        print("3. Get your API key from the dashboard")
        print("4. Run: set FAL_KEY=your_key_here")
        sys.exit(1)

    print("Generating image for vault404 article...")

    prompt = """A futuristic digital brain network visualization showing multiple AI agents
connected through glowing neural pathways. Dark tech background with blue and purple neon
highlights. The brain should be semi-transparent with visible neural connections and data
flows. Collective intelligence concept. High quality 3D render with cinematic lighting.
Professional tech illustration style. Clean, modern, minimalist. 16:9 aspect ratio."""

    try:
        # Use FLUX Pro for high quality
        result = fal_client.subscribe(
            "fal-ai/flux-pro/v1.1",
            arguments={
                "prompt": prompt,
                "image_size": "landscape_16_9",
                "num_inference_steps": 28,
                "guidance_scale": 3.5,
                "num_images": 1,
                "enable_safety_checker": True,
            },
        )

        if result and "images" in result and len(result["images"]) > 0:
            image_url = result["images"][0]["url"]
            print(f"\nImage generated successfully!")
            print(f"URL: {image_url}")
            print(f"\nDownload the image and add it to the docs folder.")

            # Try to download the image
            try:
                import httpx
                response = httpx.get(image_url)
                if response.status_code == 200:
                    output_path = os.path.join(
                        os.path.dirname(__file__),
                        "..", "docs", "vault404-hero.png"
                    )
                    with open(output_path, "wb") as f:
                        f.write(response.content)
                    print(f"\nImage saved to: {output_path}")
            except Exception as e:
                print(f"\nCouldn't auto-download: {e}")
                print("Please download manually from the URL above.")
        else:
            print("No image returned from API")
            print(f"Result: {result}")

    except Exception as e:
        print(f"Error generating image: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
