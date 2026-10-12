# DANDI Cache: `valid-nwb-file-to-byte-weighted-structure`

A mapping from the content ID of every valid HDF5 NWB file on the DANDI archive to scalars describing how that file's stored bytes are spread across its arrays and across its top-level NWB sections.

The structural caches before this one describe a file as an unlabeled tree and count its objects.
These values weight each array by its bytes instead, so that how a file is organized can be told apart from how big it is.

An **array** here is an HDF5 dataset object.
This README never uses the bare word "dataset", because it means an HDF5 object in some of this organization's repositories and a dandiset in their consumers.

Everything is computed from [`valid-nwb-file-to-array-sizes`](https://github.com/dandi-cache/valid-nwb-file-to-array-sizes), which records every array's storage bytes, section and chunking.
This cache never reads the archive, so every run rebuilds every file from that input.
Only files the input walked successfully (`walk_status` `ok`) appear here.

## Definitions

For one file, let the arrays be those recorded by `valid-nwb-file-to-array-sizes`, let $s_i$ be array $i$'s `storage_bytes`, and let $S = \sum_i s_i$ be the file's `total_storage_bytes`.
Over the arrays with $s_i > 0$, the storage share of array $i$ is

$$p_i = \frac{s_i}{S}, \qquad \sum_i p_i = 1.$$

| Field | Definition |
|---|---|
| `d0` | The number of arrays with $s_i > 0$. |
| `d1` | $\exp\left(-\sum_i p_i \ln p_i\right)$: the exponential of the Shannon entropy of the shares, the "effective number" of arrays. |
| `d2` | $1 / \sum_i p_i^2$: the inverse Simpson concentration, an effective number weighted further toward the largest arrays. |
| `evenness` | $d_1 / d_0$: 1 when every stored array holds the same number of bytes, approaching $1/d_0$ when one array holds nearly all of them. |
| `top1_share` | $\max_i p_i$: the share of stored bytes in the largest array. |
| `top5_share` | The sum of the five largest $p_i$, or of all of them when there are fewer than five. |
| `metadata_fraction` | $1 - S / B$, where $B$ is `object_size_bytes`, the blob's size from S3 `HEAD`, clamped to $[0, 1]$. This is the share of the file not allocated to array data: object headers, attributes, chunk indexes, the global heap and free space. |
| `metadata_fraction_clamped` | `true` when $1 - S/B$ fell outside $[0, 1]$ and was clamped. |
| `section_shares` | For each top-level section $k$, $\sum_{i \in k} s_i / S$. Sections are those of `valid-nwb-file-to-array-sizes`: `acquisition`, `processing`, `analysis`, `stimulus`, `intervals`, `units`, `general`, `scratch`, `specifications` and `other`. Only sections holding stored bytes appear, and the shares sum to 1. |
| `n_chunks_total` | The total number of allocated chunks over the file's chunked arrays. |
| `median_chunk_bytes` | For each chunked array with at least one chunk, its mean stored chunk size $s_i / n_i$, where $n_i$ is its `n_chunks`; then the median of those values over the file's chunked arrays. `null` when the file has no chunked array with a chunk. |

$d_0 \geq d_1 \geq d_2 \geq 1$ always holds: the three are Hill numbers of order 0, 1 and 2 of the share distribution.

A file in which no array holds a byte has `d0` of 0 and no share distribution to describe.
`d1`, `d2`, `evenness`, `top1_share` and `top5_share` are then `null`, and `section_shares` is empty.

Each line of the derivatives is a single-entry mapping:

```json
{"<content_id>": {"d0": 168, "d1": 40.28, "d2": 40.07, "evenness": 0.2398, "top1_share": 0.02498, "top5_share": 0.1249, "metadata_fraction": 0.09183, "metadata_fraction_clamped": false, "section_shares": {"acquisition": 0.4997, "general": 0.0005, "other": 0.00002, "specifications": 0.0001, "stimulus": 0.4997}, "n_chunks_total": 0, "median_chunk_bytes": null}}
```

## Dependencies

None beyond the standard library and the [`dandi-cache-utils`](https://github.com/dandi-cache/dandi-cache-utils) base image.
The image is the lighter `:latest` tag rather than `:nwb`, since this cache never opens an NWB file.

## Validation

Checked on the 197 files that `valid-nwb-file-to-array-sizes` walked successfully in its 200-file validation sample, one file from each of 200 dandisets. That cache's own validation section has the sample and its failures.

- **Sample.** 200 files sampled; 197 derived here, the other 3 having timed out in the input.
- **Array count.** The input's `n_arrays` matched `valid-nwb-file-to-number-of-datasets` for all 197: 0 mismatches.
- **Section shares.** `section_shares` sums to 1 within $10^{-9}$ for every file.
- **Metadata fraction.** It never had to be clamped, since `total_storage_bytes` never exceeded `object_size_bytes`.
- **Ordering.** $d_0 \geq d_1 \geq d_2 \geq 1$, $0 < $ `evenness` $\leq 1$ and `top1_share` $\leq$ `top5_share` $\leq 1$ hold for every file.
- **Failures.** None in this cache itself. The input's were 3 `timeout`.

The same checks also pass on the input's second sample, the first 200 valid content IDs in sorted order across 65 dandisets. All 200 walked and all 200 are derived here, with 0 array-count mismatches and no violations.



## One-time use

`dist` publishes each output as a [Zarr](https://zarr.dev/) store: the cache itself is `derivatives/valid_nwb_file_to_byte_weighted_structure.zarr/`.
A store is one array of [JSON Lines](https://jsonlines.org/) text cut into chunk files, each holding whole lines and gzip-compressed.
It can be read with the standard library alone, or opened remotely with any Zarr library.

### Python API (recommended)

The chunk files are gzip-compressed [JSON Lines](https://jsonlines.org/): list them, then read them in order as you would any JSONL files.

```python
import gzip, json, urllib.request

chunks = "https://api.github.com/repos/dandi-cache/valid-nwb-file-to-byte-weighted-structure/contents/derivatives/valid_nwb_file_to_byte_weighted_structure.zarr/stream/c?ref=dist"
files = sorted((entry["download_url"] for entry in json.load(urllib.request.urlopen(chunks))), key=lambda url: int(url.rsplit("/", 1)[1]))
valid_nwb_file_to_byte_weighted_structure = {key: value for url in files for line in gzip.decompress(urllib.request.urlopen(url).read()).decode().splitlines() if line for key, value in json.loads(line).items()}
```

### Remote Zarr store

Anything that opens Zarr can open the store over HTTP, reading only the chunks it needs.
The group's `zarr.json` carries the array's metadata, so opening it takes one request:

```bash
pip install "zarr>=3" fsspec aiohttp
```

```python
import json

import zarr

url = "https://raw.githubusercontent.com/dandi-cache/valid-nwb-file-to-byte-weighted-structure/refs/heads/dist/derivatives/valid_nwb_file_to_byte_weighted_structure.zarr"
stream = zarr.open_group(url, mode="r")["stream"]
print(stream.shape, stream.chunks)  # Bytes in all, and bytes per chunk.

# The first chunk, fetched and decompressed on its own: whole lines, each `{"<key>": <value>}`.
first_chunk = stream[: stream.chunks[0]].tobytes().decode("utf-8")
for line in first_chunk.splitlines():
    if line.strip():
        print(json.loads(line))
        break
```

Reading `stream[:]` returns the whole text; to read it in pieces, step through it by `stream.chunks[0]`, as each chunk is fetched whole.

### Save to file

A raw URL cannot be listed, so to fetch every chunk at once clone the `dist` branch, which holds nothing else:

```bash
git clone --branch dist --depth 1 https://github.com/dandi-cache/valid-nwb-file-to-byte-weighted-structure.git
```



## Repeated use

If you plan on using this cache regularly, clone the `derivatives` branch of this repository:

```bash
git clone --branch derivatives https://github.com/dandi-cache/valid-nwb-file-to-byte-weighted-structure.git
```

Or, if you prefer [DataLad](https://www.datalad.org/):

```bash
datalad clone https://github.com/dandi-cache/valid-nwb-file-to-byte-weighted-structure.git --branch derivatives
```

The `derivatives` branch also keeps the log of every update under `logs/`, next to the results it produced.

Each output is a store on the `derivatives` branch, where it is the whole log, uncompacted, and plain text:

```python
import json, pathlib

chunks = sorted(pathlib.Path("valid-nwb-file-to-byte-weighted-structure/derivatives/valid_nwb_file_to_byte_weighted_structure.zarr/stream/c").iterdir(), key=lambda path: int(path.name))
valid_nwb_file_to_byte_weighted_structure = {key: value for chunk in chunks for line in chunk.read_text().splitlines() if line for key, value in json.loads(line).items()}
```


## Reading the `derivatives` branch

Each output is kept on the `derivatives` branch as a [Zarr](https://zarr.dev/) v3 store of JSON Lines: a one-dimensional `uint8` array whose bytes are the lines, padded with newlines to the end of its last chunk.
A key recorded more than once keeps its last line, which the dictionary below does by itself.

```python
import json

import zarr  # zarr>=3, with fsspec and aiohttp to read over HTTP

url = "https://raw.githubusercontent.com/dandi-cache/valid-nwb-file-to-byte-weighted-structure/derivatives/derivatives/valid_nwb_file_to_byte_weighted_structure.zarr"
stream = zarr.open_group(url, mode="r")["stream"]
lines = stream[:].tobytes().decode("utf-8").splitlines()
valid_nwb_file_to_byte_weighted_structure = {key: value for line in lines if line for key, value in json.loads(line).items()}
```

Without Zarr, each chunk is a plain file of whole lines at `derivatives/valid_nwb_file_to_byte_weighted_structure.zarr/stream/c/<n>`, read in order of `n`.
