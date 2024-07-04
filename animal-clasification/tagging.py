import os
import random
import json
import zipfile
import cv2
import pandas as pd
import requests
from io import BytesIO
from tqdm import tqdm
from collections import defaultdict
from urllib.parse import urlparse
from megadetector.utils.url_utils import parallel_download_urls
from megadetector.data_management.lila.lila_common import is_empty


'''
suidae        389702
cervidae      186592 
felidae       135463 (Using all the prionailurus bengalisis and the rest use similar cats)
mustelidae    120260
muridae         4879 (using wellington ones)
soricidae         50 (not using this because of lack of precision)
'''
# Species of interest
species_of_interest = ['suidae']
taxonomy_rank = 'family'
# Local directories
lila_local_base = 'C:/lila'
metadata_dir = os.path.join(lila_local_base, 'metadata')
os.makedirs(metadata_dir, exist_ok=True)

output_dir = os.path.join(lila_local_base, 'lila_downloads_by_dataset')
os.makedirs(output_dir, exist_ok=True)

# Directory to save images with drawn contour boxes
output_contour_dir = os.path.join(output_dir, species_of_interest[0].replace(' ', '_'))
os.makedirs(output_contour_dir, exist_ok=True)

# Number of concurrent download threads
n_download_threads = 100
max_images_per_dataset = 10  # None
preferred_provider = 'gcp'  # 'azure', 'gcp', 'aws'

# Open parquet file
df = pd.read_parquet("C:/lila/metadata/lila_image_urls_and_labels_filtered1.parquet")

# Find all the images we want to download
common_name_to_count = defaultdict(int)
ds_name_to_urls = defaultdict(list)

def find_items(row):
    if is_empty(row[taxonomy_rank]):
        return
    match = False
    for species_name in species_of_interest:
        if species_name in row[taxonomy_rank]:
            match = True
            common_name_to_count[species_name] += 1
            break
    if match:
        ds_name_to_urls[row['dataset_name']].append(row['url_' + preferred_provider])

tqdm.pandas()
_ = df.progress_apply(find_items, axis=1)

# Flatten the list of URLs
all_urls = list(ds_name_to_urls.values())
all_urls = [item for sublist in all_urls for item in sublist]
print('Found {} matching URLs across {} datasets'.format(len(all_urls), len(ds_name_to_urls)))

for common_name in common_name_to_count:
    print('{}: {}'.format(common_name, common_name_to_count[common_name]))

from copy import deepcopy
ds_name_to_urls_raw = deepcopy(ds_name_to_urls)

# Optionally trim to a fixed number of URLs per dataset
if max_images_per_dataset is not None:
    for ds_name in ds_name_to_urls:
        if len(ds_name_to_urls[ds_name]) > max_images_per_dataset:
            ds_name_to_urls[ds_name] = random.sample(ds_name_to_urls[ds_name], max_images_per_dataset)

# %% Choose target files for each URL
from megadetector.data_management.lila.lila_common import lila_base_urls

# Choose target files for each URL
urls_to_download = set()
for ds_name in ds_name_to_urls:
    for url in ds_name_to_urls[ds_name]:
        urls_to_download.add(url)
urls_to_download = sorted(list(urls_to_download))

base_url = lila_base_urls[preferred_provider]
print(base_url)
assert base_url.endswith('/')
url_to_target_file = {}
for url in urls_to_download:
    assert url.startswith(base_url)
    target_fn_relative = url.replace(base_url, '')
    target_fn_abs = os.path.join(output_dir, target_fn_relative)
    url_to_target_file[url] = target_fn_abs

# Download image files
download_results = parallel_download_urls(
    url_to_target_file=url_to_target_file,
    verbose=False,
    overwrite=True,
    n_workers=n_download_threads,
    pool_type="thread",
)

# Load CSV file with bounding box URLs
csv_file = 'C:/lila/metadata/lila_camera_trap_datasets.csv'
bbox_df = pd.read_csv(csv_file)

# Check columns of the CSV file
print(bbox_df.columns)

# Assuming the correct column names are 'short_name' and 'mdv5b_results_raw'
dataset_column = 'short_name'
bbox_url_column = 'mdv5b_results_raw'

# Normalize the dataset names in the DataFrame
bbox_df[dataset_column] = bbox_df[dataset_column].str.lower().str.replace(' ', '-')

# Create a function to draw bounding boxes
def draw_bounding_boxes(image_path, bboxes):
    image = cv2.imread(image_path)
    for bbox in bboxes:
        x, y, w, h = bbox['bbox']
        x = int(x * image.shape[1])
        y = int(y * image.shape[0])
        w = int(w * image.shape[1])
        h = int(h * image.shape[0])
        cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)
    return image

# Process each dataset
for ds_name, urls in ds_name_to_urls.items():
    ds_name_normalized = ds_name.lower().replace(' ', '-')
    print(f"Processing dataset: {ds_name_normalized}")
    print(bbox_df[dataset_column].unique())  # Print unique values in the dataset column
    # Get the bounding box URL for the dataset
    if ds_name_normalized not in bbox_df[dataset_column].values:
        print(f"Dataset {ds_name_normalized} not found in the bounding box CSV.")
        continue
    bbox_url = bbox_df.loc[bbox_df[dataset_column] == ds_name_normalized, bbox_url_column].values[0]
    print(f"Fetching bounding boxes from: {bbox_url}")
    response = requests.get(bbox_url)
    print(f"Status code: {response.status_code}")
    if response.status_code != 200:
        print(f"Failed to fetch {bbox_url}")
        continue
    
    try:
        with zipfile.ZipFile(BytesIO(response.content)) as z:
            json_filename = [name for name in z.namelist() if name.endswith('.json')][0]
            with z.open(json_filename) as f:
                bbox_data = json.load(f)
    except Exception as e:
        print(f"Failed to process ZIP file from {bbox_url}: {e}")
        continue
    
    # Print a sample of the bbox['file'] to check the format
    if bbox_data['images']:
        print(f"Sample bbox['file']: {bbox_data['images'][0]['file']}")

    for url in urls:
        image_path = url_to_target_file[url]
        if not os.path.exists(image_path):
            continue
        # Get the bounding boxes for this image
        image_file = '/'.join(image_path.replace(output_dir, '').split('/')[1:]).replace('images/','')
        bboxes = [bbox for bbox in bbox_data['images'] if bbox['file'] == image_file]
        print(f"Image ID: {image_file}, Bounding boxes found: {len(bboxes)}")  # Debug print
        if bboxes:
            for bbox in bboxes:
                image_with_boxes = draw_bounding_boxes(image_path, bbox['detections'])
                # Save all images in the single directory with the name of the animal
                output_path = os.path.join(output_contour_dir, os.path.basename(image_path))
                cv2.imwrite(output_path, image_with_boxes)

print("Processing complete.")
