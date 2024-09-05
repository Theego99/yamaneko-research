import os
import numpy as np
import tensorflow as tf
from tensorflow.keras.preprocessing import image
import matplotlib.pyplot as plt
import cv2

# Load the trained model
model = tf.keras.models.load_model('animal_classifier_binary_model.h5')

# Define the class names
class_names = ['other', 'bird']

# Function to load and preprocess the image
def load_and_preprocess_image(img_path, target_size=(150, 150)):
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)  # Read image in grayscale
    if img is None:
        print(f"Failed to load image: {img_path}")
        return None
    img = cv2.resize(img, target_size)  # Resize image
    img = img.astype('float32') / 255.0  # Normalize to [0, 1]
    img = np.expand_dims(img, axis=-1)  # Add channel dimension for grayscale
    img = np.expand_dims(img, axis=0)  # Add batch dimension
    return img

# Function to make predictions
def predict_image(img_path):
    img_array = load_and_preprocess_image(img_path)
    if img_array is None:
        return None, None
    predictions = model.predict(img_array)
    predicted_class_index = np.argmax(predictions, axis=1)
    predicted_class = class_names[predicted_class_index[0]]
    return predicted_class, predictions[0]

# Test the model with selected images
def test_model_with_images(image_paths, threshold=0.9):
    for img_path in image_paths:
        predicted_class, probabilities = predict_image(img_path)
        if predicted_class is None:
            continue
        
        # Check the probability for the "birds" class
        bird_probability = probabilities  # Index 1 is for "birds"
        
        # Apply the threshold logic
        if bird_probability < threshold:
            predicted_class = 'bird'
        
        print(f"Image: {img_path}")
        print(f"Predicted class: {predicted_class}")
        print(f"Probabilities: {probabilities}")
        plt.imshow(cv2.imread(img_path, cv2.IMREAD_GRAYSCALE), cmap='gray')
        plt.title(f"Predicted: {predicted_class}")
        plt.axis('off')
        plt.show()

# Example usage
if __name__ == '__main__':
    # List of image paths to test
    image_paths = [
        r"C:/yamaneko-kenkyu/p_data/30052024/34.6225665-129.3414982/karasu.mp4/birds_0.53.jpg",
        r"C:/yamaneko-kenkyu/p_data/30052024/34.6225665-129.3414982/rat.AVI/birds_0.96.jpg",
        r"C:/yamaneko-kenkyu/p_data/30052024/34.6225665-129.3414982/sagi.AVI/birds_0.83.jpg",
        r"C:/yamaneko-kenkyu/p_data/30052024/34.6225665-129.3414982/tobi.AVI/birds_0.61.jpg",
        r"C:/yamaneko-kenkyu/p_data/30052024/34.6245436-129.3455148/shika.AVI/birds_0.98.jpg",
        r"C:/yamaneko-kenkyu/p_data/30052024/34.6245436-129.3455148/yamaneko.AVI/birds_0.98.jpg",
        r"C:/yamaneko-kenkyu/p_data/30052024/34.6245436-129.3455148/shikaosu.mp4/birds_0.97.jpg",
        # Add more image paths as needed
    ]
    
    # You can adjust the threshold (e.g., 0.9)
    test_model_with_images(image_paths, threshold=0.9)
