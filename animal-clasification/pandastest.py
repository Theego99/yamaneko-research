import pandas as pd

# Read the CSV file with low_memory=False to avoid DtypeWarning
# df = pd.read_csv("C:/lila/metadata/lila_image_urls_and_labels_filtered.csv")
# Read from Parquet (or HDF5)
df = pd.read_parquet("C:/lila/metadata/lila_image_urls_and_labels_filtered1.parquet")
print("CSV all read")

print("---------------------- exclude some genera not in tsushima ----------------------")
# # Define the values to drop
excluded_genera = [
    None, 'nesomys','eliurus','rhizomys','microgale','hypogeomys','otolemur','hemicentetes','lemur'
]

# # Drop rows where 'class' column contains any of the specified values
df = df[~df['genus'].isin(excluded_genera)]

print("---------------------- number of rows----------------------")
# Display the number of rows
print(len(df))

print("---------------------- getting data type of id ----------------------")
# Display the data types of the columns
print(df.dtypes)

print("---------------------- drop columns ----------------------")

# df = df.drop(columns=['url_aws', 'infraorder', 'suborder', 'infraclass','annotation_level','datetime'])

print("---------------------- drop picture with missing url ----------------------")
print(df.nunique())

# Filter out rows where 'class' is 'aves'
filtered_df = df[df['class'] != 'aves']

# Get unique values in 'genus' column
unique_values = filtered_df['genus'].unique()

unique_values_count = filtered_df['genus'].value_counts()

# Count the number of rows where the class is 'Aves'
aves_count = df[df['class'] == 'aves'].shape[0]
# Print the unique values
print("Unique values in 'genus' column:")
print(unique_values)
print('==========not aves count ========')
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
df.to_csv("C:/lila/metadata/lila_image_urls_and_labels_filtered.csv", index=False)

# Save the updated DataFrame to a more efficient format
print("=====saving to parquet=========")
df.to_parquet("C:/lila/metadata/lila_image_urls_and_labels_filtered1.parquet")

print("---------------------- owari ----------------------")
