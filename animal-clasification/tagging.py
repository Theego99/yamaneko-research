"""

lila_common.py

Common constants and functions related to LILA data management/retrieval.

"""
import os
import json
import random
import zipfile
from tqdm import tqdm
from PIL import Image
from collections import defaultdict
from urllib.parse import urlparse
import pandas as pd
from megadetector.utils.url_utils import download_url, parallel_download_urls
from megadetector.utils.path_utils import unzip_file
from megadetector.utils.ct_utils import is_empty

# LILA camera trap primary metadata file
lila_metadata_url = 'http://lila.science/wp-content/uploads/2023/06/lila_camera_trap_datasets.csv'
lila_taxonomy_mapping_url = 'https://lila.science/public/lila-taxonomy-mapping_release.csv'
lila_all_images_url = 'https://lila.science/public/lila_image_urls_and_labels.csv.zip'

wildlife_insights_page_size = 30000
wildlife_insights_taxonomy_url = 'https://api.wildlifeinsights.org/api/v1/taxonomy/taxonomies-all?fields=class,order,family,genus,species,authority,taxonomyType,uniqueIdentifier,commonNameEnglish&page[size]={}'.format(
    wildlife_insights_page_size)
wildlife_insights_taxonomy_local_json_filename = 'wi_taxonomy.json'
wildlife_insights_taxonomy_local_csv_filename = \
    wildlife_insights_taxonomy_local_json_filename.replace('.json','.csv')

# Filenames are consistent across clouds relative to these URLs
lila_base_urls = {
    'azure':'https://lilawildlife.blob.core.windows.net/lila-wildlife/',
    'gcp':'https://storage.googleapis.com/public-datasets-lila/',
    'aws':'http://us-west-2.opendata.source.coop.s3.amazonaws.com/agentmorris/lila-wildlife/'
}

lila_cloud_urls = {
    'azure':'https://lilawildlife.blob.core.windows.net/lila-wildlife/',
    'gcp':'gs://public-datasets-lila/',
    'aws':'s3://us-west-2.opendata.source.coop/agentmorris/lila-wildlife/'
}

for url in lila_base_urls.values():
    assert url.endswith('/')

preferred_provider = 'gcp'  # 'azure', 'gcp', 'aws'
n_download_threads = 20

# Local directories for metadata and output
lila_local_base = ('C:/lila')
metadata_dir = os.path.join(lila_local_base, 'metadata')
os.makedirs(metadata_dir, exist_ok=True)
output_dir = os.path.join(lila_local_base, 'lila_downloads_by_dataset').replace('\\','/')
os.makedirs(output_dir, exist_ok=True)

def read_wildlife_insights_taxonomy_mapping(metadata_dir):
    """
    Reads the WI taxonomy mapping file, downloading the .json data (and writing to .csv) if necessary.
    
    Args:
        metadata_dir (str): folder to use for temporary LILA metadata files
        
    Returns:
        pd.dataframe: A DataFrame with taxonomy information
    """
    
    wi_taxonomy_csv_path = os.path.join(metadata_dir,wildlife_insights_taxonomy_local_csv_filename)
    
    if os.path.exists(wi_taxonomy_csv_path):
        df = pd.read_csv(wi_taxonomy_csv_path)
    else:
        wi_taxonomy_json_path = os.path.join(metadata_dir,wildlife_insights_taxonomy_local_json_filename)
        download_url(wildlife_insights_taxonomy_url, wi_taxonomy_json_path)
        with open(wi_taxonomy_json_path,'r',encoding='utf-8') as f:
            d = json.load(f)
            
        # We haven't implemented paging, make sure that's not an issue
        assert d['meta']['totalItems'] < wildlife_insights_page_size
            
        # d['data'] is a list of items that look like:
        """
         {'id': 2000003,
         'class': 'Mammalia',
         'order': 'Rodentia',
         'family': 'Abrocomidae',
         'genus': 'Abrocoma',
         'species': 'bennettii',
         'authority': 'Waterhouse, 1837',
         'commonNameEnglish': "Bennett's Chinchilla Rat",
         'taxonomyType': 'biological',
         'uniqueIdentifier': '7a6c93a5-bdf7-4182-82f9-7a67d23f7fe1'}
        """
        df = pd.DataFrame(d['data'])
        df.to_csv(wi_taxonomy_csv_path,index=False)
        
    return df


def read_lila_taxonomy_mapping(metadata_dir):
    """
    Reads the LILA taxonomy mapping file, downloading the .csv file if necessary.
    
    Args:
        metadata_dir (str): folder to use for temporary LILA metadata files
        
    Returns:
        pd.DataFrame: a DataFrame with one row per identification
    """
    
    p = urlparse(lila_taxonomy_mapping_url)
    taxonomy_filename = os.path.join(metadata_dir,os.path.basename(p.path))
    download_url(lila_taxonomy_mapping_url, taxonomy_filename)
    
    df = pd.read_csv(lila_taxonomy_mapping_url)
    
    return df

   
def read_lila_metadata(metadata_dir):
    """
    Reads LILA metadata (URLs to each dataset), downloading the .csv file if necessary.
    
    Args:
        metadata_dir (str): folder to use for temporary LILA metadata files
        
    Returns:
        dict: a dict mapping dataset names (e.g. "Caltech Camera Traps") to dicts
        with keys corresponding to the headers in the .csv file, currently:
        
        - name
        - short_name
        - continent
        - country
        - region
        - image_base_url_relative
        - metadata_url_relative
        - bbox_url_relative
        - image_base_url_gcp
        - metadata_url_gcp
        - bbox_url_gcp
        - image_base_url_aws
        - metadata_url_aws
        - bbox_url_aws
        - image_base_url_azure
        - metadata_url_azure
        - box_url_azure
        - mdv4_results_raw
        - mdv5b_results_raw
        - md_results_with_rde
        - json_filename
    """
    
    # Put the master metadata file in the same folder where we're putting images
    p = urlparse(lila_metadata_url)
    metadata_filename = os.path.join(metadata_dir,os.path.basename(p.path))
    download_url(lila_metadata_url, metadata_filename)
    
    df = pd.read_csv(metadata_filename)
    
    records = df.to_dict('records')
    
    # Parse into a table keyed by dataset name
    metadata_table = {}
    
    # r = records[0]
    for r in records:
        if is_empty(r['name']):
            continue
        
        # Convert NaN's to None
        for k in r.keys():
            if is_empty(r[k]):
                r[k] = None
                
        metadata_table[r['name']] = r
    
    return metadata_table    
    

def read_lila_all_images_file(metadata_dir):
    """
    Downloads if necessary - then unzips if necessary - the .csv file with label mappings for
    all LILA files, and opens the resulting .csv file as a Pandas DataFrame.
    
    Args:
        metadata_dir (str): folder to use for temporary LILA metadata files
        
    Returns:
        pd.DataFrame: a DataFrame containing one row per identification in a LILA camera trap image
    """
        
    p = urlparse(lila_all_images_url)
    lila_all_images_zip_filename = os.path.join(metadata_dir,os.path.basename(p.path))
    download_url(lila_all_images_url, lila_all_images_zip_filename)
    
    with zipfile.ZipFile(lila_all_images_zip_filename,'r') as z:
        files = z.namelist()
    assert len(files) == 1
    
    unzipped_csv_filename = os.path.join(metadata_dir,files[0])
    if not os.path.isfile(unzipped_csv_filename):
        unzip_file(lila_all_images_zip_filename,metadata_dir)
    else:
        print('{} already unzipped'.format(unzipped_csv_filename))    
    
    df = pd.read_csv(unzipped_csv_filename)
    
    return df


def filter_images_by_species(df, species_list, max_images_per_species=5):
    common_name_to_count = defaultdict(int)
    ds_name_to_urls = defaultdict(list)
    def find_items(row):
        if is_empty(row['common_name']):
            return
        match = False
        for species_name in species_list:
            if species_name in row['common_name']:
                match = True
                # if common_name_to_count[species_name] < max_images_per_species:
                common_name_to_count[species_name] += 1
                ds_name_to_urls[row['dataset_name']].append((row['url_' + preferred_provider], row))
                break
    tqdm.pandas()
    df.progress_apply(find_items, axis=1)
    all_urls = [item[0] for sublist in ds_name_to_urls.values() for item in sublist]
    all_metadata = [item[1] for sublist in ds_name_to_urls.values() for item in sublist]
    return ds_name_to_urls, all_urls, common_name_to_count, all_metadata

def download_images(urls_to_download, output_dir):
    base_url = lila_base_urls[preferred_provider]
    base_url.replace('\\','/')
    assert base_url.endswith('/')
    url_to_target_file = {}
    for url in urls_to_download:
        assert url.startswith(base_url)
        target_fn_relative = url.replace(base_url, '')
        target_fn_abs = os.path.join(output_dir, target_fn_relative)
        url_to_target_file[url] = target_fn_abs
    download_results = parallel_download_urls(url_to_target_file=url_to_target_file, verbose=False, overwrite=False, n_workers=n_download_threads, pool_type='thread')
    return download_results

def generate_crops_from_cct(cct_file,image_dir,output_dir,padding=0,flat_output=True):
    """
    Given a .json file in COCO Camera Traps format, creates a cropped image for
    each bounding box.
    
    Args:
        cct_file (str): the COCO .json file from which we should load data
        image_dir (str): the folder where the images live; filenames in the .json
            file should be relative to this folder
        output_dir (str): the folder where we should write cropped images
        padding (float, optional): number of pixels we should expand each box before
            cropping
        flat_output (bool, optional): if False, folder structure will be preserved
            in the output, e.g. the image a/b/c/d.jpg will result in image files 
            in the output folder called, e.g., a/b/c/d_crop_000_id_12345.jpg.  If
            [flat_output] is True, the corresponding output image will be 
            a_b_c_d_crop_000_id_12345.jpg.            
    """
    
    ## Read and validate input
    
    assert os.path.isfile(cct_file)
    assert os.path.isdir(image_dir)
    os.makedirs(output_dir,exist_ok=True)

    with open(cct_file,'r') as f:
        d = json.load(f)
   
    
    ## Find annotations for each image
    
    from collections import defaultdict
    
    # This actually maps image IDs to annotations, but only to annotations
    # containing boxes
    image_id_to_boxes = defaultdict(list)
    
    n_boxes = 0
    
    for ann in d['annotations']:
        if 'bbox' in ann:
            image_id_to_boxes[ann['image_id']].append(ann)
            n_boxes += 1
            
    print('Found {} boxes in {} annotations for {} images'.format(
        n_boxes,len(d['annotations']),len(d['images'])))
    
    
    ## Generate crops
        
    # im = d['images'][0]
    for im in tqdm(d['images']):
        
        input_image_fn = os.path.join(os.path.join(image_dir,im['file_name']))
        assert os.path.isfile(input_image_fn), 'Could not find image {}'.format(input_image_fn)
        
        if im['id'] not in image_id_to_boxes:
            continue
        
        annotations_this_image = image_id_to_boxes[im['id']]
        
        # Load the image
        img = Image.open(input_image_fn)
        
        # Generate crops
        # i_ann = 0; ann = annotations_this_image[i_ann]
        for i_ann,ann in enumerate(annotations_this_image):
            
            # x/y/w/h, origin at the upper-left
            bbox = ann['bbox']
            
            xmin = bbox[0]
            ymin = bbox[1]
            xmax = xmin + bbox[2]
            ymax = ymin + bbox[3]
            
            xmin -= padding / 2
            ymin -= padding / 2
            xmax += padding / 2
            ymax += padding / 2
            
            xmin = max(xmin,0)
            ymin = max(ymin,0)
            xmax = min(xmax,img.width-1)
            ymax = min(ymax,img.height-1)
                        
            crop = img.crop(box=[xmin, ymin, xmax, ymax])
            
            output_fn = os.path.splitext(im['file_name'])[0].replace('\\','/')
            if flat_output:
                output_fn = output_fn.replace('/','_')
            output_fn = output_fn + '_crop' + str(i_ann).zfill(3) + '_id_' + ann['id']
            output_fn = output_fn + '.jpg'
                
            output_full_path = os.path.join(output_dir,output_fn)
            
            if not flat_output:
                os.makedirs(os.path.dirname(output_full_path),exist_ok=True)
                
            crop.save(output_full_path)
            
        # ...for each box
        
    # ...for each image


def read_metadata_file_for_dataset(ds_name,
                                   metadata_dir,
                                   metadata_table=None,
                                   json_url=None,
                                   preferred_cloud='gcp'):
    """
    Downloads if necessary - then unzips if necessary - the .json file for a specific dataset.
    
    Args:
        ds_name (str): the name of the dataset for which you want to retrieve metadata (e.g.
            "Caltech Camera Traps")        
        metadata_dir (str): folder to use for temporary LILA metadata files
        metadata_table (dict, optional): an optional dictionary already loaded via
            read_lila_metadata()
        json_url (str, optional): the URL of the metadata file, if None will be retrieved
            via read_lila_metadata()
        preferred_cloud (str, optional): 'gcp' (default), 'azure', or 'aws'
        
    Returns:
        str: the .json filename on the local disk
    
    """
    
    assert preferred_cloud in lila_base_urls.keys()
    
    if json_url is None:
        
        if metadata_table is None:
            metadata_table = read_lila_metadata(metadata_dir)
            
        json_url = metadata_table[ds_name]['metadata_url_' + preferred_cloud]
    
    p = urlparse(json_url)
    json_filename = os.path.join(metadata_dir,os.path.basename(p.path))
    download_url(json_url, json_filename)
    
    # Unzip if necessary
    if json_filename.endswith('.zip'):
        
        with zipfile.ZipFile(json_filename,'r') as z:
            files = z.namelist()
        assert len(files) == 1
        unzipped_json_filename = os.path.join(metadata_dir,files[0])
        if not os.path.isfile(unzipped_json_filename):
            unzip_file(json_filename,metadata_dir)        
        else:
            print('{} already unzipped'.format(unzipped_json_filename))
        json_filename = unzipped_json_filename
    
    return json_filename

if __name__ == "__main__":
    # Read metadata and taxonomy information
    print("Reading metadata and taxonomy information...")
    wi_taxonomy_df = read_wildlife_insights_taxonomy_mapping(metadata_dir)
    lila_taxonomy_df = read_lila_taxonomy_mapping(metadata_dir)
    lila_metadata_dict = read_lila_metadata(metadata_dir)
    lila_images_df = read_lila_all_images_file(metadata_dir)
    # Filter images by specific species
    species_of_interest = ['grey fox', 'gray fox', 'cape fox', 'red fox', 'kit fox']
    print("Filtering images by species...")
    ds_name_to_urls, all_urls, common_name_to_count, all_metadata = filter_images_by_species(lila_images_df, species_of_interest, max_images_per_species=5)
    print('Found {} matching URLs across {} datasets'.format(len(all_urls), len(ds_name_to_urls)))
    for common_name in common_name_to_count:
        print('{}: {}'.format(common_name, common_name_to_count[common_name]))
    # Select only a few images per species for demonstration
    selected_urls = []
    selected_metadata = []
    for urls in ds_name_to_urls.values():
        selected_urls.extend([url for url, metadata in urls[:5]])
        selected_metadata.extend([metadata for url, metadata in urls[:5]])
    # Download the selected images
    print("Downloading selected images...")
    download_results = download_images(selected_urls, output_dir)
    # Generate cropped images based on bounding boxes
    print("Generating cropped images...")
    for ds_name in ds_name_to_urls:
        json_file = read_metadata_file_for_dataset(ds_name, metadata_dir, lila_metadata_dict)
        generate_crops_from_cct(json_file, output_dir, os.path.join(output_dir, 'crops'))
    
    # Print metadata of each image including species and bounding boxes
    print("Metadata for selected images:")
    for metadata in selected_metadata:
        print(json.dumps(metadata, indent=2))
