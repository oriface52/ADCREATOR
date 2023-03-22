import os
from flask import Flask, render_template, request, session, make_response
from io import BytesIO
import openai
import io
import base64
import requests
import json
from PIL import Image, ImageFont, ImageDraw, ImageOps

app = Flask(__name__)

# Your Kakao Brain REST API key
REST_API_KEY = "1b9db5aa6058d896a726f3a5e017c849"
openai.api_key = "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"
app.secret_key = 'your_secret_key_here'

# Helper functions for image conversion
def imageToString(img):
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    my_encoded_img = base64.encodebytes(img_byte_arr.getvalue()).decode('ascii')
    return my_encoded_img

def stringToImage(base64_string, mode):
    if base64_string is None:
        return None
    imgdata = base64.b64decode(base64_string)
    image = Image.open(io.BytesIO(imgdata))
    image = image.convert(mode)
    return image


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/generate", methods=["POST"])
def generate():
    # Get prompt input
    inputs = request.form.getlist('input')
    prompt = "\n".join(inputs)

    # Generate text prompts
    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )
    text_choices = completion.choices[0].message.content

    # Save the text choices to the session
    session['text_choices'] = text_choices

    return render_template("index.html", text_choices=text_choices)

@app.route("/inpainting", methods=["POST"])
def inpainting():
    # Get image and mask files from form
    image_file = request.files["image"]
    mask_file = request.files["mask"]

    # Load images with PIL
    image = Image.open(image_file)
    mask = Image.open(mask_file)

    # Convert images to base64 strings
    image_base64 = imageToString(image)
    mask_base64 = imageToString(mask)

    # Prompt text to use
    prompt_text = request.form.get("text")

    # Call the Kakao Brain API
    response = requests.post(
        'https://api.kakaobrain.com/v1/inference/karlo/inpainting',
        json={
            'prompt': {
                'image': image_base64,
                'mask': mask_base64,
                'text': prompt_text,
                'batch_size': 1
            }
        },
        headers={
            'Authorization': f'KakaoAK {REST_API_KEY}',
            'Content-Type': 'application/json'
        }
    )

    # Convert response to JSON and extract the first image
    response_json = json.loads(response.content)
    result_image_base64 = response_json["images"][0]["image"]

    # Convert the result image from base64 to PIL format
    result_image = stringToImage(result_image_base64, mode="RGB")

    # Resize the result image to 315x258
    result_image_resized = result_image.resize((315, 258))

    # Create the ad banner
    banner = Image.new('RGB', (1029, 258), color=(255, 255, 255))

    # Get the sentence and image from the session
    sentence = session.get('text_choices')

    try:
        # Create a new image with the same size as the banner and fill it with the background color
        background = Image.new('RGB', banner.size, (250, 250, 250))

        # Resize the image
        result_image_resized = ImageOps.fit(result_image, (320, 190), method=Image.LANCZOS)

        # Add rounded borders to the image
        result_image_rounded = ImageOps.fit(result_image_resized, (320, 190), method=Image.LANCZOS)
        mask = Image.new('L', result_image_rounded.size, 0)
        draw = ImageDraw.Draw(mask) 
        draw.rounded_rectangle((0, 0) + result_image_rounded.size, radius=0, fill=255)
        result_image_rounded.putalpha(mask)

        # Calculate coordinates to center the image on the banner
        x_offset = (banner.size[0] - result_image_rounded.size[0]) // 11 * 10
        y_offset = (banner.size[1] - result_image_rounded.size[1]) // 2

        # Paste the image onto the banner
        background.paste(result_image_rounded, (x_offset, y_offset))

        # Add text to the banner
        font_path = os.path.join(os.path.dirname(__file__), 'font', 'SpoqaHanSansNeo-Bold.otf')
        font = ImageFont.truetype(font_path, size=37)
        draw = ImageDraw.Draw(background)
        draw.text((40, y_offset+70), sentence, font=font, fill=(76, 76, 76))

        # Convert the banner to a base64-encoded string
        banner_base64 = imageToString(background)

        # Store the banner image in session
        session['banner_image'] = banner_base64

        # Display the banner image
        return render_template("index.html", banner_image=banner_base64)




    except Exception as e:
        # Handle errors
        print("Error:", e)
        return render_template("error.html", message="Failed to create banner", error=str(e))





# Download the ad banner
@app.route("/download_bizboard")
def download_bizboard():

    # Get the banner image from the session
    banner_base64 = session.get('banner_image')

    # Convert the banner image from base64 to PIL format
    banner_image = stringToImage(banner_base64, mode="RGB")

    # Create a BytesIO object to hold the image bytes
    img_byte_io = BytesIO()

    # Save the banner image to the BytesIO object as a PNG
    banner_image.save(img_byte_io, 'PNG')
    img_byte_io.seek(0)

    # Create a Flask response object with the image bytes
    response = make_response(img_byte_io.getvalue())

    # Set the response headers to force a download
    response.headers.set('Content-Type', 'image/png')
    response.headers.set('Content-Disposition', 'attachment', filename='bizboard.png')

    return response

if __name__ == '__main__':
    app.run(debug=True)
