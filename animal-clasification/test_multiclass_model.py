import tensorflow as tf
import numpy as np
import cv2
import os
from tensorflow.keras.preprocessing import image

# Load the trained model
model = tf.keras.models.load_model("multiclass_classifier_model.keras")

# Define class names based on the trained model
class_names = ["birds", "deer", "others", "boar"]


# Preprocess images: convert to grayscale and resize to the target size
def preprocess_image(image_path, target_size=(150, 150)):
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)  # Load the image in grayscale
    if img is None:
        print(f"Failed to load image: {image_path}")
        return None
    img = cv2.resize(img, target_size)  # Resize the image to target size
    img = img.astype("float32") / 255.0  # Normalize pixel values to [0, 1]
    img = np.expand_dims(img, axis=-1)  # Add channel dimension (1 for grayscale)
    img = np.expand_dims(img, axis=0)  # Add batch dimension
    return img


# Test the model with a few images
def test_model(image_paths):
    for img_path in image_paths:
        preprocessed_img = preprocess_image(img_path)
        if preprocessed_img is None:
            continue

        # Predict the class for the image
        predictions = model.predict(preprocessed_img)
        predicted_class = np.argmax(predictions, axis=1)
        confidence = predictions[0][predicted_class][
            0
        ]  # Confidence score for the predicted class

        print(f"Image: {img_path}")
        print(f"Predicted class: {class_names[predicted_class[0]]}")
        print(f"Confidence: {confidence:.5f}")
        print("-----------------------------")


# Example usage with a few images
if __name__ == "__main__":
    image_paths = [
        r"C:/yamaneko-kenkyu/p_data/30052024/34.6225665-129.3414982/karasu.mp4/bird_0.53.jpg",
        r"C:/yamaneko-kenkyu/p_data/30052024/34.6225665-129.3414982/rat.AVI/other_0.93.jpg",
        r"C:/yamaneko-kenkyu/p_data/30052024/34.6225665-129.3414982/sagi.AVI/bird_0.75.jpg",
        r"C:/yamaneko-kenkyu/p_data/30052024/34.6225665-129.3414982/tobi.AVI/bird_0.55.jpg",
        r"C:/yamaneko-kenkyu/p_data/30052024/34.6245436-129.3455148/shika.AVI/other_0.97.jpg",
        r"C:/yamaneko-kenkyu/p_data/30052024/34.6245436-129.3455148/yamaneko.AVI/other_0.98.jpg",
        r"C:/yamaneko-kenkyu/p_data/30052024/34.6245436-129.3455148/shikaosu.mp4/other_0.97.jpg",

    ]
    test_model(image_paths)
