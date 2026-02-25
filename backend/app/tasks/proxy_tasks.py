"""
代理相关任务
- 批量检测代理
"""
import time
import logging
from typing import List
from datetime import datetime

from sqlmodel import Session
from app.core.db import engine
from app.core.celery_app import celery_app
from app.models.proxy import Proxy
from app.services.proxy_checker import check_proxy_connectivity

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2)
def check_proxies_batch_task(self, proxy_ids: List[int]):
    """
    批量检测代理连通性
    """
    logger.info(f"Checking {len(proxy_ids)} proxies")
    
    results = {"success": 0, "failed": 0, "errors": []}
    
    with Session(engine) as session:
        for proxy_id in proxy_ids:
            proxy = session.get(Proxy, proxy_id)
            if not proxy:
                results["errors"].append(f"Proxy {proxy_id} not found")
                results["failed"] += 1
                continue
            
            try:
                # Rate limiting for ip-api.com
                time.sleep(1.5)
                
                is_alive, error_msg, details = check_proxy_connectivity(proxy, fetch_details=True)
                
                proxy.last_checked = datetime.utcnow()
                
                if is_alive:
                    proxy.status = "active"
                    proxy.fail_count = 0
                    results["success"] += 1
                    
                    if details:
                        if details.get('country'):
                            proxy.country = details.get('country')
                        
                        hosting = details.get('hosting', False)
                        isp = details.get('isp', '')
                        if hosting:
                            proxy.provider_type = "datacenter"
                        elif isp:
                            proxy.provider_type = "isp"
                            
                else:
                    proxy.status = "dead"
                    proxy.fail_count = (proxy.fail_count or 0) + 1
                    results["failed"] += 1
                
                session.add(proxy)
                session.commit()
                
            except Exception as e:
                logger.error(f"Error checking proxy {proxy_id}: {e}")
                proxy.status = "dead"
                proxy.fail_count = (proxy.fail_count or 0) + 1
                session.add(proxy)
                session.commit()
                results["failed"] += 1
                results["errors"].append(str(e))
    
    logger.info(f"Proxy check completed: {results['success']} success, {results['failed']} failed")
    return results
