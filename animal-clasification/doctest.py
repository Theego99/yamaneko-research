"""
download a list of files from LILA, e.g. all the files
in a data set corresponding to a particular species.

"""
import os
import random
from urllib.parse import urlparse
from megadetector.utils.url_utils import parallel_download_urls
import pandas as pd
from tqdm import tqdm
from collections import defaultdict

from megadetector.data_management.lila.lila_common import \
     is_empty

lila_base_urls = {
    'azure':'https://lilawildlife.blob.core.windows.net/lila-wildlife/ena24',
    'gcp':'https://storage.googleapis.com/public-datasets-lila/ena24',
    'aws':'http://us-west-2.opendata.source.coop.s3.amazonaws.com/agentmorris/lila-wildlife/ena24'
}

# If any of these strings appear in the common name of a species, we'll download that image
species_of_interest = ['prionailurus bengalensis']

# We'll write images, metadata downloads, and temporary files here
lila_local_base = 'C:/lila'

metadata_dir = os.path.join(lila_local_base,'metadata')
os.makedirs(metadata_dir,exist_ok=True)

output_dir = os.path.join(lila_local_base,'lila_downloads_by_dataset')
os.makedirs(output_dir,exist_ok=True)

# Number of concurrent download threads
n_download_threads = 20
max_images_per_dataset = 10 # None
preferred_provider = 'gcp' # 'azure', 'gcp', 'aws'

# open parquet file
df = pd.read_parquet("C:\lila\metadata\lila_image_urls_and_labels_filtered1.parquet" )


# Find all the images we want to download

common_name_to_count = defaultdict(int)
ds_name_to_urls = defaultdict(list)
def find_items(row):
    if is_empty(row['scientific_name']):
        return
    match = False
    # we're checking whether each row is on a list of species of interest, but you do you.
    for species_name in species_of_interest:
        if species_name in row['scientific_name']:
            match = True
            common_name_to_count[species_name] += 1
            break
    
    if match:
        ds_name_to_urls[row['dataset_name']].append(row['url_' + preferred_provider])
tqdm.pandas()
_ = df.progress_apply(find_items,axis=1)
# We have a list of URLs for each dataset, flatten them all into a list of URLs
all_urls = list(ds_name_to_urls.values())
all_urls = [item for sublist in all_urls for item in sublist]
print('Found {} matching URLs across {} datasets'.format(len(all_urls),len(ds_name_to_urls)))



for common_name in common_name_to_count:
    print('{}: {}'.format(common_name,common_name_to_count[common_name]))

from copy import deepcopy
ds_name_to_urls_raw = deepcopy(ds_name_to_urls)


# %% Optionally trim to a fixed number of URLs per dataset

if max_images_per_dataset is None:
    pass
else:
    # ds_name = next(iter(ds_name_to_urls.keys()))
    for ds_name in ds_name_to_urls:
        if len(ds_name_to_urls[ds_name]) > max_images_per_dataset:
            ds_name_to_urls[ds_name] = random.sample(ds_name_to_urls[ds_name],max_images_per_dataset)


# %% Choose target files for each URL

from megadetector.data_management.lila.lila_common import lila_base_urls

# We have a list of URLs per dataset, flatten that into a single list of URLs
urls_to_download = set()
for ds_name in ds_name_to_urls:
    for url in ds_name_to_urls[ds_name]:
        urls_to_download.add(url)
urls_to_download = sorted(list(urls_to_download))        

# A URL might look like this:
# https://storage.googleapis.com/public-datasets-lila/wcs-unzipped/animals/0667/0302.jpg
# We'll write that to an output file that looks like this (relative to output_dir):
# wcs-unzipped/animals/0667/0302.jpg
# ...so we need to remove the base URL to get the target file.

base_url = lila_base_urls[preferred_provider]
assert base_url.endswith('/')
url_to_target_file = {}
for url in urls_to_download:
    assert url.startswith(base_url) 
    target_fn_relative = url.replace(base_url,'')
    target_fn_abs = os.path.join(output_dir,target_fn_relative)
    url_to_target_file[url] = target_fn_abs
# Download image files
download_results = parallel_download_urls(
    url_to_target_file=url_to_target_file,
    verbose=False,
    overwrite=True,
    n_workers=n_download_threads,
    pool_type="thread",
)
