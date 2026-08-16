"""Optimal Matching 거리와 CLARA식 대표 시퀀스로 커리어 궤적을 유형화한다."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform
from sklearn.metrics import silhouette_score


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "data" / "clean" / "career_sequences.json"
OUTPUT = ROOT / "data" / "clean" / "career_trajectory_clusters.json"
SEED = 42

REGULAR = {"regular_small", "regular_medium", "regular_large", "regular_unknown"}


def substitution(a: str, b: str) -> float:
    if a == b:
        return 0.0
    if a in REGULAR and b in REGULAR:
        return 0.7
    if {a, b} <= (REGULAR | {"non_regular"}):
        return 1.2
    if "not_employed" in (a, b):
        return 2.0
    return 1.6


def om_distance(a: list[str], b: list[str], indel: float = 1.0) -> float:
    previous = np.arange(len(b) + 1, dtype=float) * indel
    for i, left in enumerate(a, 1):
        current = np.empty(len(b) + 1, dtype=float)
        current[0] = i * indel
        for j, right in enumerate(b, 1):
            current[j] = min(
                previous[j] + indel, current[j - 1] + indel,
                previous[j - 1] + substitution(left, right),
            )
        previous = current
    return float(previous[-1] / max(len(a), len(b), 1))


def distance_matrix(sequences: list[list[str]]) -> np.ndarray:
    n = len(sequences)
    matrix = np.zeros((n, n), dtype=np.float32)
    for i in range(n):
        for j in range(i):
            matrix[i, j] = matrix[j, i] = om_distance(sequences[i], sequences[j])
    return matrix


def trajectory_label(medoid: list[str]) -> str:
    counts = Counter(medoid)
    broad = [("regular" if state in REGULAR else state) for state in medoid]
    transitions = sum(a != b for a, b in zip(broad, broad[1:]))
    if counts["not_employed"] >= len(medoid) / 2:
        return "미취업 반복형"
    if counts["self_employed"] >= len(medoid) / 2:
        return "자영업 지속형"
    if counts["non_regular"] >= len(medoid) / 2:
        return "비상용 고용형"
    if medoid[-1] == "regular_large" and medoid[0] != "regular_large":
        return "대규모 상향 이동형"
    if transitions >= max(3, len(medoid) // 2):
        return "고용상태 전환 반복형"
    if sum(state in REGULAR for state in medoid) >= len(medoid) * .7:
        return "상용직 안정형"
    return "혼합 경로형"


def main() -> None:
    raw = json.loads(SOURCE.read_text(encoding="utf-8"))
    people = raw["sequences"]
    sequences = [item["states"] for item in people]
    rng = np.random.default_rng(SEED)
    sample_size = min(550, len(people))
    sample_idx = np.sort(rng.choice(len(people), sample_size, replace=False))
    sample_sequences = [sequences[i] for i in sample_idx]
    distances = distance_matrix(sample_sequences)
    tree = linkage(squareform(distances, checks=False), method="average")

    candidates = []
    for k in range(4, 7):
        labels = fcluster(tree, k, criterion="maxclust") - 1
        score = float(silhouette_score(distances, labels, metric="precomputed"))
        candidates.append((score, k, labels))
    silhouette, k, sample_labels = max(candidates, key=lambda item: item[0])

    medoid_sample_indices = []
    for cluster in range(k):
        members = np.flatnonzero(sample_labels == cluster)
        local = distances[np.ix_(members, members)]
        medoid_sample_indices.append(int(members[np.argmin(local.mean(axis=1))]))
    medoids = [sample_sequences[i] for i in medoid_sample_indices]

    assignments, assignment_distance = [], []
    for sequence in sequences:
        values = [om_distance(sequence, medoid) for medoid in medoids]
        assignments.append(int(np.argmin(values)))
        assignment_distance.append(round(float(min(values)), 4))

    clusters = []
    used_labels: dict[str, int] = {}
    for cluster, medoid in enumerate(medoids):
        members = [i for i, value in enumerate(assignments) if value == cluster]
        base_label = trajectory_label(medoid)
        used_labels[base_label] = used_labels.get(base_label, 0) + 1
        label = base_label if used_labels[base_label] == 1 else f"{base_label} {used_labels[base_label]}"
        state_counts = Counter(state for i in members for state in sequences[i])
        clusters.append({
            "id": cluster, "label": label, "member_n": len(members), "medoid_states": medoid,
            "state_share": {state: round(count / sum(state_counts.values()), 4) for state, count in state_counts.items()},
            "mean_assignment_distance": round(float(np.mean([assignment_distance[i] for i in members])), 4),
        })

    result = {
        "version": 1, "method": "Optimal Matching + average-link sample clustering + medoid assignment",
        "sample_n": sample_size, "people_n": len(people), "selected_k": k,
        "sample_silhouette": round(silhouette, 4),
        "k_candidates": {str(item[1]): round(item[0], 4) for item in candidates},
        "clusters": clusters,
        "assignments": [
            {"pid": people[i]["pid"], "cluster_id": assignments[i], "distance": assignment_distance[i]}
            for i in range(len(people))
        ],
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print(f"[완료] k={k}, silhouette={silhouette:.3f}")
    for cluster in clusters:
        print(cluster["id"], cluster["label"], cluster["member_n"], cluster["medoid_states"])


if __name__ == "__main__":
    main()
