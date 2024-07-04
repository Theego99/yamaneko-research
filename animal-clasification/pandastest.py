import pandas as pd

# Read the CSV file with low_memory=False to avoid DtypeWarning
# df = pd.read_csv("C:/lila/metadata/lila_image_urls_and_labels_filtered.csv")
# Read from Parquet (or HDF5)
df = pd.read_parquet("C:/lila/metadata/lila_image_urls_and_labels_filtered1.parquet")
print("CSV all read")

print("---------------------- exclude some genera not in tsushima ----------------------")
# # Define the values to drop
excluded_genera = [
    None,'sus barbatus','cervus canadensis','parahyaena brunnea','felis chaus'
]

# # Drop rows where 'class' column contains any of the specified values
# df = df[~df['scientific_name'].isin(excluded_genera)]

print("---------------------- exclude some bird families not in tsushima ----------------------")
bird_families_to_keep = [
    "gaviidae",
    "apodidae",
    "podicipedidae",
    "cuculidae",
    "anatidae",
    "phasianidae",
    "picidae",
    "ciconiidae",
    "ardeidae",
    "threskiornithidae",
    "fringillidae",
    "prunellidae",
    "cettiidae",
    "aegithalidae",
    "monarchidae",
    "muscicapidae",
    "corvidae",
    "oriolidae",
    "paridae",
    "motacillidae",
    "turdidae",
    "hirundinidae",
    "remizidae",
    "ploceidae",
    "alaudidae",
    "pycnonotidae",
    "emberizidae",
    "troglodytidae",
    "sturnidae",
    "zosteropidae",
    "laniidae",
    "pittidae",
    "bombycillidae",
    "accipitridae",
    "falconidae",
    "alcidae",
    "diomedeidae",
    "scolopacidae",
    "recurvirostridae",
    "rostratulidae",
    "charadriidae",
    "glareolidae",
    "stercorariidae",
    "phalaropodidae",
    "haematopodidae",
    "jacanidae",
    "rallidae",
    "gruidae",
    "columbidae",
    "strigidae",
    "alcedinidae",
    "coraciidae",
    "upupidae",
    "phalacrocoracidae",
    "sulidae",
    "pelecanidae",
    "procellariidae",
    "caprimulgidae",
]
# df = df[(df['class'] != 'aves') | (df['family'].isin(bird_families_to_keep))]

print("---------------------- number of rows----------------------")
# Display the number of rows
print(len(df))

print("---------------------- getting data type of id ----------------------")
# Display the data types of the columns
print(df.dtypes)

print("---------------------- drop columns ----------------------")

# df = df.drop(columns=['original_label'])

# print("---------------------- drop picture with missing url ----------------------")
print(df.nunique())

# Filter out rows where 'class' is 'aves'
filtered_df = df[df['class'] != 'aves']


unique_values_count = filtered_df['family'].value_counts()

# Count the number of rows where the class is 'Aves'
not_aves_count = df[df['class'] != 'aves'].shape[0]


# Print the unique values
print('==========not aves count ========')
print(unique_values_count)
print('========== not aves count ========')
print(not_aves_count)

# Filter out rows where 'class' is not 'aves'
filtered_df = df[df['class'] == 'aves']

# Get unique values in 'genus' column
unique_values = filtered_df['species'].unique()

unique_values_count = filtered_df['family'].value_counts()

# Count the number of rows where the class is not 'Aves'
aves_count = df[df['class'] == 'aves'].shape[0]

print("Unique values in 'genus' column:")
print(unique_values)
print('========== aves count ========')
print(unique_values_count)
print('========== aves count ========')
print(aves_count)

# columns_list =['url_gcp']
# # Drop rows where all specified columns are empty
# df = df.dropna(subset=columns_list, how='all')
# print("---------------------- drop pics with missing family, genus and species ----------------------")
# columns_list =['species','genus','family']
# # Drop rows where all specified columns are empty
# df = df.dropna(subset=columns_list, how='all')


'''
dataset_name       object
url_gcp            object
image_id           object
original_label     object
scientific_name    object
common_name        object
phylum             object
class              object
order              object
family             object
genus              object
species            object
dtype: object
'''

# # Dictionary to store the counts of each genus
# genus_counts = {genus: 0 for genus in genera_list}

# # Count the instances of each genus
# for genus in genera_list:
#     genus_counts[genus] = df['genus'].str.contains(genus, case=False, na=False).sum()

# # Print the counts
# for genus, count in genus_counts.items():
#     print(f"{genus}: {count}")


# Save the updated DataFrame to a new CSV file
print("======saving to csv=======")
# df.to_csv("C:/lila/metadata/lila_image_urls_and_labels_filtered.csv", index=False)

# Save the updated DataFrame to a more efficient format
print("=====saving to parquet=========")
# df.to_parquet("C:/lila/metadata/lila_image_urls_and_labels_filtered1.parquet")

print("---------------------- owari ----------------------")
