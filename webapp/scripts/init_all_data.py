
import logging
import math
import random
import sys as sys_mod
import os
from datetime import datetime, timedelta, date

sys_mod.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from webapp.tools.mongo import DATABASE
from bson import ObjectId

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def main():
    db = DATABASE
    
    # 1. Customers
    print("=== 1. 客户数据 ===")
    db.customers.delete_many({})
    customer_data = []
    for i, (name, short, utype, ind, volt, reg, dist, addr, contact, phone, status) in enumerate([
        ("苏州工业园区华兴科技有限公司", "华兴科技", "工商业", "制造业", "10kV", "苏州市", "工业园区", "苏州工业园区星海街200号", "李明", "13912345678", "active"),
        ("南京钢铁集团股份有限公司", "南钢集团", "大工业", "钢铁", "110kV", "南京市", "六合区", "南京市六合区卸甲甸", "王强", "13912345679", "active"),
    ]):
        doc = {
            "_id": ObjectId(),
            "user_name": name, "short_name": short, "user_type": utype, "industry": ind,
            "voltage": volt, "region": reg, "district": dist, "address": addr,
            "contact_person": contact, "contact_phone": phone,
            "status": status, "created_at": datetime(2026, 6, 1), "updated_at": datetime(2026, 7, 1),
            "created_by": "admin", "updated_by": "admin",
            "utility_accounts": []
        }
        customer_data.append(doc)
    db.customers.insert_many(customer_data)
    print(f"  Created {len(customer_data)} customers (partial)")

if __name__ == "__main__":
    main()
