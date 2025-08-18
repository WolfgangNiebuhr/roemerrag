# File aus postgtes exportieren: kubectl exec -n experimental postgres-77cd9df5d7-9xrjx -- psql -U admin -d vector_db -c "COPY (SELECT Vector::text FROM vectors) TO STDOUT WITH CSV;" > vector_export.csv

import pandas as pd
import ast
import random
import numpy as np
from sklearn.decomposition import PCA
import matplotlib.pyplot as plt
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_distances
from sklearn.metrics.pairwise import cosine_similarity

df = pd.read_csv("vector_export.csv", header=None, on_bad_lines='warn')
df[0] = df[0].apply(ast.literal_eval)  # Annahme: Vektor steht in Spalte 0

vector_df = pd.DataFrame(df[0].to_list())
vektor_normen = np.linalg.norm(vector_df, axis=1)
print("Durchschnittliche Norm:", np.mean(vektor_normen))
print("Standardabweichung der Norm:", np.std(vektor_normen))

dimension_means = np.mean(vector_df, axis=0)
dimension_stds = np.std(vector_df, axis=0)

pca = PCA(n_components=2)
reduced = pca.fit_transform(vector_df)

plt.scatter(reduced[:, 0], reduced[:, 1], s=5)
plt.title("PCA-Reduktion der Vektoren")
plt.show()


dist_matrix = cosine_distances(vector_df)
clustering = DBSCAN(metric='precomputed', eps=0.3, min_samples=5)
labels = clustering.fit_predict(dist_matrix)

print("Anzahl gefundener Cluster:", len(set(labels)) - (1 if -1 in labels else 0))


idx = random.sample(range(len(vector_df)), 1000)
sample = vector_df.iloc[idx]
similarity_matrix = cosine_similarity(sample)
similarities = similarity_matrix[np.triu_indices_from(similarity_matrix, k=1)]

plt.hist(similarities, bins=50)
plt.title("Verteilung der Cosinus-Ähnlichkeit")
plt.xlabel("Cosinus-Ähnlichkeit")
plt.ylabel("Häufigkeit")
plt.show()