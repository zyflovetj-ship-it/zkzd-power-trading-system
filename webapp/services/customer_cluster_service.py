import logging
import math
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List

from pymongo.database import Database

from webapp.models.customer_cluster import ClusterData, ClusterConfig, ClusterResultItem, ClusterSummary

logger = logging.getLogger(__name__)


class CustomerClusterService:

    def __init__(self, db: Database) -> None:
        self.db = db
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        try:
            existing = {idx.get('name') for idx in self.db.user_load_data.list_indexes()}
            if 'idx_cc_load' not in existing:
                self.db.user_load_data.create_index(
                    [('user_name', 1), ('timestamp', 1)],
                    name='idx_cc_load',
                )
        except Exception as exc:
            logger.warning("创建客户聚类索引时出错: %s", exc)

    def cluster_customers(self, n_clusters: int = 3, features: List[str] = None) -> Dict[str, Any]:
        if features is None:
            features = ["peak_valley_ratio", "load_rate", "volatility"]

        config = ClusterConfig(n_clusters=n_clusters, features=features)
        customers = self._extract_features()

        if len(customers) < n_clusters:
            results = [ClusterResultItem(
                customer_id=c["customer_id"],
                customer_name=c["customer_name"],
                cluster=0,
                features=c["features"]
            ) for c in customers]
            return ClusterData(config=config, results=results, summary=[]).model_dump()

        feature_vectors = []
        for c in customers:
            vec = [c["features"].get(f, 0) for f in features]
            feature_vectors.append(vec)

        labels = self._kmeans(feature_vectors, n_clusters)

        results = []
        cluster_data: Dict[int, List] = {i: [] for i in range(n_clusters)}
        for i, c in enumerate(customers):
            label = labels[i]
            results.append(ClusterResultItem(
                customer_id=c["customer_id"],
                customer_name=c["customer_name"],
                cluster=label,
                features=c["features"]
            ))
            cluster_data[label].append(c["features"])

        summary = []
        for cid in range(n_clusters):
            feats_list = cluster_data[cid]
            count = len(feats_list)
            avg_pvr = sum(f.get("peak_valley_ratio", 0) for f in feats_list) / count if count else 0
            avg_lr = sum(f.get("load_rate", 0) for f in feats_list) / count if count else 0
            avg_vol = sum(f.get("volatility", 0) for f in feats_list) / count if count else 0
            summary.append(ClusterSummary(
                cluster_id=cid,
                count=count,
                avg_peak_valley_ratio=round(avg_pvr, 4),
                avg_load_rate=round(avg_lr, 4),
                avg_volatility=round(avg_vol, 4)
            ))

        return ClusterData(config=config, results=results, summary=summary).model_dump()

    def _extract_features(self) -> List[dict]:
        """
        从 user_load_data 集合按 user_name 提取负荷特征。
        分析依据：近30天负荷数据，计算三个特征：
          - peak_valley_ratio: 峰谷比 = 最大负荷 / 最小负荷
          - load_rate: 负荷率 = 平均负荷 / 最大负荷
          - volatility: 波动性 = 标准差 / 均值（变异系数）
        """
        customers = []
        try:
            end = datetime.now()
            start = end - timedelta(days=30)

            pipeline = [
                {"$match": {"timestamp": {"$gte": start, "$lte": end}}},
                {"$group": {
                    "_id": "$user_name",
                    "values": {"$push": "$load_value"},
                }},
                {"$sort": {"_id": 1}},
            ]
            grouped = list(self.db.user_load_data.aggregate(pipeline))

            for g in grouped:
                cname = g["_id"]
                if not cname:
                    continue
                raw_values = [v for v in g.get("values", []) if v is not None]
                if not raw_values:
                    continue

                max_v = max(raw_values)
                min_v = min(raw_values)
                avg_v = sum(raw_values) / len(raw_values)

                peak_valley_ratio = max_v / min_v if min_v > 0 else 0
                load_rate = avg_v / max_v if max_v > 0 else 0

                variance = sum((v - avg_v) ** 2 for v in raw_values) / len(raw_values)
                volatility = math.sqrt(variance) / avg_v if avg_v > 0 else 0

                customers.append({
                    "customer_id": cname,
                    "customer_name": cname,
                    "features": {
                        "peak_valley_ratio": round(peak_valley_ratio, 4),
                        "load_rate": round(load_rate, 4),
                        "volatility": round(volatility, 4),
                    }
                })
        except Exception as exc:
            logger.warning("提取聚类特征失败: %s", exc)
        return customers

    def _kmeans(self, data: List[List[float]], k: int, max_iter: int = 50) -> List[int]:
        n = len(data)
        dim = len(data[0]) if data else 0
        if n == 0 or dim == 0:
            return []

        indices = random.sample(range(n), min(k, n))
        centroids = [data[i][:] for i in indices]

        labels = [0] * n
        for _ in range(max_iter):
            new_labels = []
            for point in data:
                dists = [sum((point[d] - c[d]) ** 2 for d in range(dim)) for c in centroids]
                new_labels.append(dists.index(min(dists)))

            if new_labels == labels:
                break
            labels = new_labels

            for j in range(k):
                cluster_points = [data[i] for i in range(n) if labels[i] == j]
                if cluster_points:
                    centroids[j] = [sum(p[d] for p in cluster_points) / len(cluster_points) for d in range(dim)]

        return labels
