"""
中长期负荷预测模拟数据生成脚本

生成未来6个月的中长期负荷预测数据并插入数据库。
"""

import logging
from datetime import datetime
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from webapp.services.medium_long_term_load_forecast_service import (
    MediumLongTermLoadForecastService,
)
from webapp.models.medium_long_term_load_forecast import (
    MediumLongTermLoadForecastCreate,
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def generate_sample_data():
    """生成中长期负荷预测模拟数据"""
    try:
        service = MediumLongTermLoadForecastService()

        # 获取当前日期
        current_date = datetime.now()
        forecast_date = current_date.strftime("%Y-%m-%d")

        # 创建预测数据请求
        # 基础负荷值设为 5000 MW，置信区间为10%
        forecast_request = MediumLongTermLoadForecastCreate(
            forecast_date=forecast_date,
            forecast_horizon_months=6,  # 未来6个月
            base_load_value=5000.0,  # 基础负荷值 5000 MW
            confidence_interval_ratio=0.1,  # 10% 置信区间
        )

        logger.info(f"开始生成中长期负荷预测数据...")
        logger.info(f"预测发布日期: {forecast_date}")
        logger.info(f"预测时间范围: {forecast_request.forecast_horizon_months} 个月")
        logger.info(f"基础负荷值: {forecast_request.base_load_value} MW")
        logger.info(f"置信区间: ±{forecast_request.confidence_interval_ratio * 100}%")

        # 创建预测数据
        result = service.create_forecast(forecast_request)

        logger.info(f"✅ 成功生成中长期负荷预测数据!")
        logger.info(f"预测发布日期: {result.forecast_date}")
        logger.info(f"预测月份数: {result.total_months}")

        # 打印预测数据
        logger.info("\n预测数据详情:")
        logger.info("-" * 80)
        for point in result.data:
            logger.info(
                f"{point.month} | 预测值: {point.forecast_value:.2f} MW | "
                f"上限: {point.upper_bound:.2f} MW | 下限: {point.lower_bound:.2f} MW"
            )
        logger.info("-" * 80)

        return True

    except Exception as e:
        logger.error(f"❌ 生成模拟数据失败: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("中长期负荷预测模拟数据生成脚本")
    logger.info("=" * 80)

    success = generate_sample_data()

    if success:
        logger.info("\n✅ 模拟数据生成完成!")
        logger.info("您现在可以通过以下API访问预测数据:")
        logger.info("  - GET /api/v1/medium-long-term-load-forecast/latest")
        logger.info("  - GET /api/v1/medium-long-term-load-forecast")
        sys.exit(0)
    else:
        logger.error("\n❌ 模拟数据生成失败!")
        sys.exit(1)
