import os
import pandas as pd
from wildlife_tools.data import WildlifeDataset
import torchvision.transforms as T
import timm
from wildlife_tools.features import DeepFeatures
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score

# Define the base directory for your dataset
base_dir = 'C:/lila/lila_downloads_by_dataset/training/wildlife-tools'

# Create metadata from your dataset (assuming the 'birds' and 'others' directories)
# This will create a pandas DataFrame with image paths and labels
data = []
for label in ['birds', 'others']:
    label_dir = os.path.join(base_dir, label)
    for img_file in os.listdir(label_dir):
        if img_file.endswith(('.png', '.jpg', '.jpeg')):  # Adjust based on image formats
            data.append([os.path.join(label_dir, img_file), label])

# Create a DataFrame with 'image_path' and 'label' columns
metadata = pd.DataFrame(data, columns=['image_path', 'label'])

# Define image transformations
transform = T.Compose([
    T.Resize([224, 224]), 
    T.ToTensor(), 
    T.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225))
])

# Create WildlifeDataset object with metadata and transformation
dataset = WildlifeDataset(metadata=metadata, root=base_dir, transform=transform)

# Load a pre-trained model for feature extraction
extractor = DeepFeatures(timm.create_model('hf-hub:BVRA/MegaDescriptor-T-224', num_classes=0, pretrained=True))

# Extract features from dataset
features = extractor(dataset)

# Split data into training and testing sets
X_train, X_test, y_train, y_test = train_test_split(features.data, features.labels, test_size=0.2)

# Train a logistic regression classifier
classifier = LogisticRegression()
classifier.fit(X_train, y_train)

# Make predictions and evaluate
y_pred = classifier.predict(X_test)
print("Accuracy:", accuracy_score(y_test, y_pred))
