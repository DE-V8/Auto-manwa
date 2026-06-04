import os
from PIL import Image, ImageDraw

def create_dummy_panel(text: str, bg_color: tuple, size: tuple = (1080, 2200)) -> Image:
    """
    Creates a simple vertical colored panel image with some text.
    """
    img = Image.new("RGB", size, bg_color)
    draw = ImageDraw.Draw(img)
    
    # Draw simple design shapes (resembling a manhwa layout)
    draw.rectangle([100, 100, 980, 2100], outline=(255, 255, 255), width=5)
    
    # Draw some circles/rectangles representing characters
    draw.ellipse([340, 500, 740, 900], fill=(200, 200, 250), outline=(255, 255, 255), width=3) # Character head
    draw.rectangle([290, 900, 790, 1500], fill=(150, 150, 220), outline=(255, 255, 255), width=3) # Character body
    
    # Draw panel number text
    # Draw text using fallback
    draw.text((450, 1600), text, fill=(255, 255, 255))
    
    return img

def main():
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'sample_chapter')
    os.makedirs(output_dir, exist_ok=True)
    
    # Create 5 panels with different colors
    panels_info = [
        ("001.jpg", (40, 44, 52)),      # Dark Grey
        ("002.jpg", (80, 20, 20)),      # Dark Red
        ("003.jpg", (20, 80, 20)),      # Dark Green
        ("004.jpg", (20, 20, 80)),      # Dark Blue
        ("005.jpg", (60, 40, 80))       # Purple
    ]
    
    print(f"Generating 5 dummy panel images in '{output_dir}'...")
    for filename, color in panels_info:
        path = os.path.join(output_dir, filename)
        panel_img = create_dummy_panel(f"PANEL: {filename}", color)
        panel_img.save(path)
        print(f"Saved: {path}")

if __name__ == "__main__":
    main()
