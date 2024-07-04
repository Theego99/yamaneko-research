import os
import random
from urllib.parse import urlparse
from megadetector.utils.url_utils import parallel_download_urls
import pandas as pd
from tqdm import tqdm
from collections import defaultdict
from PIL import Image
import json

from megadetector.data_management.lila.lila_common import is_empty

lila_base_urls = {
    'azure': 'https://lilawildlife.blob.core.windows.net/lila-wildlife/',
    'gcp': 'https://storage.googleapis.com/public-datasets-lila/',
    'aws': 'http://us-west-2.opendata.source.coop.s3.amazonaws.com/agentmorris/lila-wildlife/'
}

species_of_interest = ['lidae']
taxonomy_row = 'family'

lila_local_base = 'C:/lila'

metadata_dir = os.path.join(lila_local_base, 'metadata')
os.makedirs(metadata_dir, exist_ok=True)

output_dir = os.path.join(lila_local_base, 'lila_downloads_by_dataset')
os.makedirs(output_dir, exist_ok=True)

n_download_threads = 20
max_images_per_dataset = 10  # None
preferred_provider = 'gcp'  # 'azure', 'gcp', 'aws'

df = pd.read_parquet("C:/lila/metadata/lila_image_urls_and_labels_filtered1.parquet")

common_name_to_count = defaultdict(int)
ds_name_to_urls = defaultdict(list)

def find_items(row):
    if is_empty(row[taxonomy_row]):
        return
    match = False
    for species_name in species_of_interest:
        if species_name in row[taxonomy_row]:
            match = True
            common_name_to_count[species_name] += 1
            break
    if match:
        ds_name_to_urls[row['dataset_name']].append(row['url_' + preferred_provider])

tqdm.pandas()
_ = df.progress_apply(find_items, axis=1)
all_urls = list(ds_name_to_urls.values())
all_urls = [item for sublist in all_urls for item in sublist]
print('Found {} matching URLs across {} datasets'.format(len(all_urls), len(ds_name_to_urls)))

for common_name in common_name_to_count:
    print('{}: {}'.format(common_name, common_name_to_count[common_name]))

from copy import deepcopy

ds_name_to_urls_raw = deepcopy(ds_name_to_urls)

if max_images_per_dataset is None:
    pass
else:
    for ds_name in ds_name_to_urls:
        if len(ds_name_to_urls[ds_name]) > max_images_per_dataset:
            ds_name_to_urls[ds_name] = random.sample(ds_name_to_urls[ds_name], max_images_per_dataset)

urls_to_download = set()
for ds_name in ds_name_to_urls:
    for url in ds_name_to_urls[ds_name]:
        urls_to_download.add(url)
urls_to_download = sorted(list(urls_to_download))

base_url = lila_base_urls[preferred_provider]
if not base_url.endswith('/'):
    base_url += '/'

# Print a few URLs to debug
print("Base URL:", base_url)
print("Sample URLs:", urls_to_download[:5])

# Filter URLs that do not match the base URL
urls_to_download = [url for url in urls_to_download if url.startswith(base_url)]

# If no URLs match, print a message and exit
if not urls_to_download:
    print("No URLs match the base URL. Exiting.")
    exit()

url_to_target_file = {}
for url in urls_to_download:
    target_fn_relative = url.replace(base_url, '')
    target_fn_abs = os.path.join(output_dir, target_fn_relative)
    url_to_target_file[url] = target_fn_abs

download_results = parallel_download_urls(
    url_to_target_file=url_to_target_file,
    verbose=False,
    overwrite=True,
    n_workers=n_download_threads,
    pool_type="thread",
)

print("Download completed. Now processing bounding boxes...")

def generate_crops_from_cct(cct_file, image_dir, output_dir, padding=0, flat_output=True):
    assert os.path.isfile(cct_file)
    assert os.path.isdir(image_dir)
    os.makedirs(output_dir, exist_ok=True)

    with open(cct_file, 'r') as f:
        d = json.load(f)

    from collections import defaultdict

    image_id_to_boxes = defaultdict(list)
    n_boxes = 0

    for ann in d['annotations']:
        if 'bbox' in ann:
            image_id_to_boxes[ann['image_id']].append(ann)
            n_boxes += 1

    print('Found {} boxes in {} annotations for {} images'.format(
        n_boxes, len(d['annotations']), len(d['images'])))

    for im in tqdm(d['images']):
        input_image_fn = os.path.join(image_dir, im['file_name'])
        if not os.path.isfile(input_image_fn):
            print(f"Could not find image {input_image_fn}, skipping.")
            continue

        if im['id'] not in image_id_to_boxes:
            continue

        annotations_this_image = image_id_to_boxes[im['id']]
        img = Image.open(input_image_fn)

        for i_ann, ann in enumerate(annotations_this_image):
            bbox = ann['bbox']
            xmin = bbox[0]
            ymin = bbox[1]
            xmax = xmin + bbox[2]
            ymax = ymin + bbox[3]

            xmin -= padding / 2
            ymin -= padding / 2
            xmax += padding / 2
            ymax += padding / 2

            xmin = max(xmin, 0)
            ymin = max(ymin, 0)
            xmax = min(xmax, img.width - 1)
            ymax = min(ymax, img.height - 1)

            crop = img.crop(box=[xmin, ymin, xmax, ymax])
            output_fn = os.path.splitext(im['file_name'])[0].replace('/', '_')
            if flat_output:
                output_fn = output_fn.replace('/', '_')
            output_fn = output_fn + '_crop' + str(i_ann).zfill(3) + '_id_' + str(ann['id']) + '.jpg'

            output_full_path = os.path.join(output_dir, output_fn)
            if not flat_output:
                os.makedirs(os.path.dirname(output_full_path), exist_ok=True)

            crop.save(output_full_path)

print("Bounding box processing completed.")

# metadata_json_file = os.path.join(metadata_dir, 'your_metadata_file.json')

# generate_crops_from_cct(metadata_json_file, output_dir, os.path.join(output_dir, 'crops'))
