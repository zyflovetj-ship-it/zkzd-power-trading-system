from datetime import timedelta

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from webapp.tools.mongo import DATABASE as db
from webapp.tools.logging_config import configure_logging
from webapp.api import v1
from webapp.api import v1_rpa_monitor
from webapp.api import v1_short_term_load_forecast
from webapp.api import v1_price_forecast
from webapp.api import v1_day_ahead_price_forecast
from webapp.api import v1_monthly_price_forecast
from webapp.api import v1_trading_contract_curve
from webapp.api import v1_trading_monthly_strategy
from webapp.api import v1_trading_d2_strategy
from webapp.api import v1_trading_day_ahead_strategy
from webapp.api import v1_review_medium_long_term
from webapp.api import v1_risk_position
from webapp.api import v1_risk_exposure
from webapp.api import v1_risk_engine
from webapp.api import v1_data_validation
from webapp.api import v1_forecast_accuracy
from webapp.api import v1_scheduler
from webapp.api import v1_spot_review
from webapp.api import v1_settlement_wholesale
from webapp.api import v1_settlement_bill_review
from webapp.api import v1_settlement_retail
from webapp.api import v1_settlement_profit
from webapp.api import v1_customer_cluster
from webapp.api import v1_load_validation
from webapp.api import v1_system_users
from webapp.api import v1_system_model_parameters
from webapp.api import v1_dashboard

# Import security functions and models from the new security tool
from webapp.tools.security import (
    Token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    authenticate_user,
    create_access_token,
    get_current_active_user,
)

# --- Initialization ---

# 全局日志初始化（方案A）
configure_logging()

def get_real_ip(request: Request) -> str:
    if "x-forwarded-for" in request.headers:
        return request.headers["x-forwarded-for"].split(',')[0].strip()
    return get_remote_address(request)

limiter = Limiter(key_func=get_real_ip, default_limits=["1000 per minute"])

app = FastAPI(
    title="zkzd电力交易系统API",
    description="为前端提供数据接口服务",
    version="1.0.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API Routes ---

@app.post("/token", response_model=Token, tags=["Authentication"])
@limiter.limit("5/minute")
async def login_for_access_token(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/v1/token", response_model=Token, tags=["Authentication"])
@limiter.limit("5/minute")
async def login_for_access_token_v1(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    """兼容前端API调用的token端点"""
    return await login_for_access_token(request, form_data)

# Include v1 routers
app.include_router(v1.public_router)
app.include_router(v1.router, dependencies=[Depends(get_current_active_user)])
app.include_router(v1_rpa_monitor.router, prefix="/api/v1/rpa", tags=["RPA监控"])
app.include_router(v1_price_forecast.router, prefix="/api/v1/price-forecast", dependencies=[Depends(get_current_active_user)])
app.include_router(v1_day_ahead_price_forecast.router, prefix="/api/v1/day-ahead-forecast", dependencies=[Depends(get_current_active_user)])
app.include_router(v1_monthly_price_forecast.router, prefix="/api/v1/monthly-forecast", dependencies=[Depends(get_current_active_user)])
app.include_router(v1_trading_contract_curve.router, prefix="/api/v1/trading/contract-curve", dependencies=[Depends(get_current_active_user)])
app.include_router(v1_trading_monthly_strategy.router, prefix="/api/v1/trading/monthly-strategy", dependencies=[Depends(get_current_active_user)])
app.include_router(v1_trading_d2_strategy.router, prefix="/api/v1/trading/d2-strategy", dependencies=[Depends(get_current_active_user)])
app.include_router(v1_trading_day_ahead_strategy.router, prefix="/api/v1/trading/day-ahead-strategy", dependencies=[Depends(get_current_active_user)])
app.include_router(v1_review_medium_long_term.router, prefix="/api/v1/review/medium-long-term", dependencies=[Depends(get_current_active_user)])

# 新增模块（此前为前端演示数据，现补齐真实后端）
app.include_router(v1_risk_position.router, prefix="/api/v1/risk/position-contracts", dependencies=[Depends(get_current_active_user)])
app.include_router(v1_risk_exposure.router, prefix="/api/v1/risk/exposure", dependencies=[Depends(get_current_active_user)])
app.include_router(v1_risk_engine.router, prefix="/api/v1", dependencies=[Depends(get_current_active_user)])
app.include_router(v1_data_validation.router, prefix="/api/v1", dependencies=[Depends(get_current_active_user)])
app.include_router(v1_forecast_accuracy.router, prefix="/api/v1", dependencies=[Depends(get_current_active_user)])
app.include_router(v1_scheduler.router, prefix="/api/v1", dependencies=[Depends(get_current_active_user)])
app.include_router(v1_spot_review.router, prefix="/api/v1/review/spot", dependencies=[Depends(get_current_active_user)], tags=["现货交易复盘"])
app.include_router(v1_settlement_wholesale.router, prefix="/api/v1/settlement/wholesale", dependencies=[Depends(get_current_active_user)])
app.include_router(v1_settlement_bill_review.router, prefix="/api/v1/settlement/bill-review", dependencies=[Depends(get_current_active_user)])
app.include_router(v1_settlement_retail.router, prefix="/api/v1/settlement/retail", dependencies=[Depends(get_current_active_user)])
app.include_router(v1_settlement_profit.router, prefix="/api/v1/settlement/profit", dependencies=[Depends(get_current_active_user)])
app.include_router(v1_customer_cluster.router, prefix="/api/v1/customer-cluster", dependencies=[Depends(get_current_active_user)])
app.include_router(v1_load_validation.router, prefix="/api/v1/basic-data/load-validation", dependencies=[Depends(get_current_active_user)])
app.include_router(v1_system_users.router, prefix="/api/v1/system/users", dependencies=[Depends(get_current_active_user)])
app.include_router(v1_system_model_parameters.router, prefix="/api/v1/system/model-parameters", dependencies=[Depends(get_current_active_user)])
app.include_router(v1_dashboard.router, prefix="/api/v1/dashboard", tags=["交易总览"], dependencies=[Depends(get_current_active_user)])



# --- Scheduler Lifecycle ---
from webapp.services.scheduler_service import SchedulerService

_scheduler_service: SchedulerService | None = None


@app.on_event("startup")
async def startup_scheduler():
    """启动 APScheduler，并把运行中的实例注册给 v1_scheduler。

    否则 v1_scheduler 会另建一个从未 start() 的实例，
    导致手动触发/改期/启停全部失效。
    """
    global _scheduler_service
    _scheduler_service = SchedulerService(db)
    _scheduler_service.start()
    v1_scheduler.set_scheduler_service(_scheduler_service)


@app.on_event("shutdown")
async def shutdown_scheduler():
    global _scheduler_service
    if _scheduler_service:
        _scheduler_service.stop()

@app.get("/", tags=["Root"], summary="应用根路径")
def read_root():
    return {"message": "欢迎使用zkzd电力交易系统API"}

# Trigger reload 3
