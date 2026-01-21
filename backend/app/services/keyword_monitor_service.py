from typing import List, Optional
from sqlmodel import Session, select
from app.models.keyword_monitor import KeywordMonitor, KeywordMonitorCreate, KeywordMonitorUpdate, KeywordHit, KeywordHitBase

class KeywordMonitorService:
    def __init__(self, session: Session):
        self.session = session

    def create_monitor(self, monitor_create: KeywordMonitorCreate) -> KeywordMonitor:
        db_monitor = KeywordMonitor.from_orm(monitor_create)
        self.session.add(db_monitor)
        self.session.commit()
        self.session.refresh(db_monitor)
        return db_monitor

    def get_monitor(self, monitor_id: int) -> Optional[KeywordMonitor]:
        return self.session.get(KeywordMonitor, monitor_id)

    def get_monitors(self, skip: int = 0, limit: int = 100) -> List[KeywordMonitor]:
        statement = select(KeywordMonitor).offset(skip).limit(limit)
        return self.session.exec(statement).all()

    def get_active_monitors(self) -> List[KeywordMonitor]:
        statement = select(KeywordMonitor).where(KeywordMonitor.is_active == True)
        return self.session.exec(statement).all()

    def update_monitor(self, monitor_id: int, monitor_update: KeywordMonitorUpdate) -> Optional[KeywordMonitor]:
        db_monitor = self.get_monitor(monitor_id)
        if not db_monitor:
            return None
        
        monitor_data = monitor_update.dict(exclude_unset=True)
        for key, value in monitor_data.items():
            setattr(db_monitor, key, value)
            
        self.session.add(db_monitor)
        self.session.commit()
        self.session.refresh(db_monitor)
        return db_monitor

    def delete_monitor(self, monitor_id: int) -> bool:
        db_monitor = self.get_monitor(monitor_id)
        if not db_monitor:
            return False
        self.session.delete(db_monitor)
        self.session.commit()
        return True

    def create_hit(self, hit_data: KeywordHitBase) -> KeywordHit:
        db_hit = KeywordHit.from_orm(hit_data)
        self.session.add(db_hit)
        self.session.commit()
        self.session.refresh(db_hit)
        return db_hit

    def get_hits(self, skip: int = 0, limit: int = 100, status: Optional[str] = None) -> List[KeywordHit]:
        statement = select(KeywordHit)
        if status:
            statement = statement.where(KeywordHit.status == status)
        statement = statement.order_by(KeywordHit.detected_at.desc()).offset(skip).limit(limit)
        return self.session.exec(statement).all()
