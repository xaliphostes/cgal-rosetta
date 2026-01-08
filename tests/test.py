import cgal
import glob
import os

# Load all fault surfaces from the faults folder
faults_dir = "./faults"
fault_files = sorted(glob.glob(os.path.join(faults_dir, "*.obj")),
                     key=lambda x: int(os.path.basename(x).replace(".obj", "")))

print(f"Loading {len(fault_files)} fault surfaces...")
meshes = [cgal.loadMesh(f) for f in fault_files]
print(f"Loaded {len(meshes)} meshes")

# Find all intersecting pairs using bounding box optimization
print("Finding intersecting pairs...")
result = cgal.intersectN(meshes)
intersecting_pairs = result[1]

print(f"Found {len(intersecting_pairs)} intersecting pairs:")
for pair in intersecting_pairs:
    print(f"  Mesh {pair[0]} <-> Mesh {pair[1]}")

# Remeshing parameters
target_edge_length = 0.01  # Adjust based on your model scale
nb_iterations = 3

# Process each intersecting pair: intersect and remesh while preserving intersection edges
print(f"\nProcessing {len(intersecting_pairs)} intersecting pairs (intersect + constrained remesh)...")
processed_meshes = list(meshes)  # Start with original meshes

for idx, pair in enumerate(intersecting_pairs):
    i, j = pair[0], pair[1]
    print(f"  Processing pair {idx+1}/{len(intersecting_pairs)}: Mesh {i} <-> Mesh {j}")

    # Intersect and remesh the pair while preserving intersection edges
    result_pair = cgal.intersectAndRemeshPair(
        processed_meshes[i],
        processed_meshes[j],
        target_edge_length,
        nb_iterations
    )

    # Update the meshes with the processed versions
    processed_meshes[i] = result_pair[0]
    processed_meshes[j] = result_pair[1]

# Save all processed surfaces
print("\nSaving processed surfaces...")
for i, mesh in enumerate(processed_meshes):
    cgal.saveMesh(mesh, f"processed_{i+1}.obj")

print(f"Done! Saved {len(processed_meshes)} processed surfaces with preserved intersection edges.")
