"""How the stored bytes of every valid NWB file are spread across its arrays and NWB sections.

Computed entirely from `valid-nwb-file-to-array-sizes`, which records every array's storage bytes,
section and chunking. Nothing here reads the archive, so the whole cache is rebuilt from that input
on every run rather than resumed: a run costs seconds, and a definition changed here reaches every
file at once.

An "array" is an HDF5 dataset object. The word "dataset" is avoided on purpose, since this
organization uses it in the HDF5 sense and its consumers use it for a dandiset.

Only files the input walked successfully are recorded. A file it could not walk has no arrays to
weigh, and gets a row here once a later run of the input succeeds.
"""

import math
import statistics

import dandi_cache_utils as dandi_cache


def byte_weighted_structure(record: dict, /) -> dict:
    """The byte-weighted summary of one file's array-sizes record. See the README for definitions."""
    arrays = record["arrays"]
    total_storage_bytes = record["total_storage_bytes"]
    stored = [array for array in arrays if array["storage_bytes"] > 0]

    if total_storage_bytes > 0:
        shares = sorted((array["storage_bytes"] / total_storage_bytes for array in stored), reverse=True)
        d1 = math.exp(-sum(share * math.log(share) for share in shares))
        d2 = 1 / sum(share * share for share in shares)
        evenness = d1 / len(shares)
        top1_share = shares[0]
        top5_share = sum(shares[:5])
        section_bytes: dict[str, int] = {}
        for array in stored:
            section_bytes[array["section"]] = section_bytes.get(array["section"], 0) + array["storage_bytes"]
        section_shares = {section: size / total_storage_bytes for section, size in sorted(section_bytes.items())}
    else:
        # No array holds a byte, so there is no distribution to describe rather than a degenerate one.
        d1 = d2 = evenness = top1_share = top5_share = None
        section_shares = {}

    object_size_bytes = record.get("object_size_bytes")
    if object_size_bytes:
        unclamped = 1 - total_storage_bytes / object_size_bytes
        metadata_fraction = min(max(unclamped, 0.0), 1.0)
        metadata_fraction_clamped = metadata_fraction != unclamped
    else:
        metadata_fraction = None
        metadata_fraction_clamped = False

    chunked = [array for array in arrays if array["layout"] == "chunked"]
    mean_chunk_bytes = [array["storage_bytes"] / array["n_chunks"] for array in chunked if array["n_chunks"]]

    return {
        "d0": len(stored),
        "d1": d1,
        "d2": d2,
        "evenness": evenness,
        "top1_share": top1_share,
        "top5_share": top5_share,
        "metadata_fraction": metadata_fraction,
        "metadata_fraction_clamped": metadata_fraction_clamped,
        "section_shares": section_shares,
        "n_chunks_total": sum(array["n_chunks"] or 0 for array in chunked),
        "median_chunk_bytes": statistics.median(mean_chunk_bytes) if mean_chunk_bytes else None,
    }


def main() -> None:
    dataset, _arguments = dandi_cache.open_dataset()

    # The array sizes are read one file at a time, never whole: at full coverage they would take
    # tens of gigabytes in memory. They come in key order, so the cache is written in that order too.
    dandi_cache.run_full_rebuild(
        dataset,
        build=lambda: [
            {content_id: byte_weighted_structure(record)}
            for content_id, record in dataset.iter_input()
            if record.get("walk_status") == "ok"
        ],
    )


if __name__ == "__main__":
    main()
