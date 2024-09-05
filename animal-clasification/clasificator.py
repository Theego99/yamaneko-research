import os
import tensorflow as tf
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras import layers, models, regularizers
from tensorflow.keras.callbacks import LearningRateScheduler, EarlyStopping
import matplotlib.pyplot as plt
import cv2

# Define the base directory
base_dir = 'C:/lila/lila_downloads_by_dataset'
training_dir = os.path.join(base_dir, 'training_binary')

# Create the training directory
os.makedirs(training_dir, exist_ok=True)

# Define the categories for binary classification: birds vs non-birds
categories = ['aves', 'cervidae', 'felidae', 'muridae', 'mustelidae', 'prionailurus_bengalensis', 'suidae']
class_names = ['birds', 'non_birds']

# Create subdirectories to map categories to 'birds' and 'non_birds'
mapping = {
    'aves': 'birds',
    'cervidae': 'non_birds',
    'felidae': 'non_birds',
    'muridae': 'non_birds',
    'mustelidae': 'non_birds',
    'prionailurus_bengalensis': 'non_birds',
    'suidae': 'non_birds'
}

# Preprocess images: convert to grayscale and resize to a fixed size
def preprocess_image(image_path, target_size=(150, 150)):
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)  # Read image in grayscale
    if image is None:
        print(f"Failed to load image: {image_path}")
        return None
    image = cv2.resize(image, target_size)  # Resize image
    return image

# Create a new directory structure for ImageDataGenerator
for category in categories:
    target_dir = os.path.join(training_dir, mapping[category])
    os.makedirs(target_dir, exist_ok=True)
    source_dir = os.path.join(base_dir, category, 'crops')
    if not os.path.exists(source_dir):
        print(f"Directory {source_dir} does not exist, skipping.")
        continue
    for filename in os.listdir(source_dir):
        source_path = os.path.join(source_dir, filename)
        target_path = os.path.join(target_dir, filename)
        preprocessed_image = preprocess_image(source_path)
        if preprocessed_image is not None:
            cv2.imwrite(target_path, preprocessed_image)  # Save preprocessed image

# Image data generator with validation split and data augmentation for birds
datagen = ImageDataGenerator(
    rescale=1./255,
    validation_split=0.2,
    horizontal_flip=True,  # Data augmentation: horizontal flip
    rotation_range=20,  # Data augmentation: rotation
    width_shift_range=0.2,  # Data augmentation: width shift
    height_shift_range=0.2  # Data augmentation: height shift
)

# Training generator
train_generator = datagen.flow_from_directory(
    training_dir,
    target_size=(150, 150),
    batch_size=20,
    color_mode='grayscale',
    class_mode='binary',
    subset='training'
)

# Validation generator
validation_generator = datagen.flow_from_directory(
    training_dir,
    target_size=(150, 150),
    batch_size=20,
    color_mode='grayscale',
    class_mode='binary',
    subset='validation'
)

# Learning rate scheduler
def scheduler(epoch, lr):
    if epoch < 10:
        return lr
    else:
        return lr * 0.1

lr_scheduler = LearningRateScheduler(scheduler)

# Early stopping
early_stopping = EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True)

# Simplified model architecture for binary classification
model = models.Sequential([
    layers.Conv2D(32, (3, 3), activation='relu', input_shape=(150, 150, 1)),
    layers.MaxPooling2D((2, 2)),
    layers.Conv2D(64, (3, 3), activation='relu'),
    layers.MaxPooling2D((2, 2)),
    layers.Conv2D(128, (3, 3), activation='relu'),
    layers.MaxPooling2D((2, 2)),
    layers.Flatten(),
    layers.Dense(128, activation='relu', kernel_regularizer=regularizers.l2(0.001)),
    layers.Dropout(0.5),
    layers.Dense(1, activation='sigmoid')  # Binary classification: birds vs non-birds
])

model.compile(loss='binary_crossentropy',
              optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
              metrics=['accuracy'])

history = model.fit(
    train_generator,
    steps_per_epoch=train_generator.samples // train_generator.batch_size,
    epochs=20,
    validation_data=validation_generator,
    validation_steps=validation_generator.samples // validation_generator.batch_size,
    callbacks=[lr_scheduler, early_stopping]
)

# Save the model
model.save('animal_classifier_binary_model.h5')

# Plotting training and validation accuracy and loss
acc = history.history['accuracy']
val_acc = history.history['val_accuracy']
loss = history.history['loss']
val_loss = history.history['val_loss']

epochs_range = range(len(acc))

plt.figure(figsize=(8, 8))
plt.subplot(1, 2, 1)
plt.plot(epochs_range, acc, label='Training Accuracy')
plt.plot(epochs_range, val_acc, label='Validation Accuracy')
plt.legend(loc='lower right')
plt.title('Training and Validation Accuracy')

plt.subplot(1, 2, 2)
plt.plot(epochs_range, loss, label='Training Loss')
plt.plot(epochs_range, val_loss, label='Validation Loss')
plt.legend(loc='upper right')
plt.title('Training and Validation Loss')
plt.show()
