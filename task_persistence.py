import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from database import SessionLocal, engine
from models import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TaskExecution(Base):
    """Database model for task execution history"""
    __tablename__ = "task_executions"
    
    id = Column(Integer, primary_key=True, index=True)
    profile_name = Column(String, nullable=False, index=True)
    scheduled_time = Column(DateTime, nullable=False, index=True)
    actual_start_time = Column(DateTime, nullable=True)
    completion_time = Column(DateTime, nullable=True)
    success = Column(Boolean, default=False)
    missed = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)
    orders_processed = Column(Integer, default=0)
    duration_seconds = Column(Float, nullable=True)
    task_type = Column(String, default="order_check")  # For future extensibility
    metadata_json = Column(Text, nullable=True)  # Store additional task-specific data
    created_at = Column(DateTime, default=datetime.now)

class TaskPersistenceManager:
    """Manages task execution persistence in database"""
    
    def __init__(self):
        self.SessionLocal = SessionLocal
        self._ensure_table_exists()
    
    def _ensure_table_exists(self):
        """Ensure the task_executions table exists"""
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Task execution table ensured")
        except Exception as e:
            logger.error(f"Error creating task execution table: {e}")
    
    def save_task_execution(self, task_data: Dict) -> Optional[int]:
        """Save a task execution record to database"""
        db = self.SessionLocal()
        try:
            # Calculate duration if both start and completion times are available
            duration_seconds = None
            if task_data.get('actual_start_time') and task_data.get('completion_time'):
                start_time = task_data['actual_start_time']
                end_time = task_data['completion_time']
                if isinstance(start_time, str):
                    start_time = datetime.fromisoformat(start_time)
                if isinstance(end_time, str):
                    end_time = datetime.fromisoformat(end_time)
                duration_seconds = (end_time - start_time).total_seconds()
            
            # Prepare metadata
            metadata = {}
            if 'orders_processed' in task_data:
                metadata['orders_processed'] = task_data['orders_processed']
            if 'total_buttons' in task_data:
                metadata['total_buttons'] = task_data['total_buttons']
            
            task_execution = TaskExecution(
                profile_name=task_data['profile_name'],
                scheduled_time=task_data['scheduled_time'] if isinstance(task_data['scheduled_time'], datetime) 
                              else datetime.fromisoformat(task_data['scheduled_time']),
                actual_start_time=task_data.get('actual_start_time'),
                completion_time=task_data.get('completion_time'),
                success=task_data.get('success', False),
                missed=task_data.get('missed', False),
                error_message=task_data.get('error_message'),
                orders_processed=task_data.get('orders_processed', 0),
                duration_seconds=duration_seconds,
                task_type=task_data.get('task_type', 'order_check'),
                metadata_json=json.dumps(metadata) if metadata else None
            )
            
            db.add(task_execution)
            db.commit()
            db.refresh(task_execution)
            
            logger.debug(f"Saved task execution {task_execution.id} for profile {task_data['profile_name']}")
            return task_execution.id
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error saving task execution: {e}")
            return None
        finally:
            db.close()
    
    def get_task_history(self, profile_name: str, limit: int = 50, 
                        include_missed: bool = True) -> List[Dict]:
        """Get task execution history for a profile"""
        db = self.SessionLocal()
        try:
            query = db.query(TaskExecution).filter(
                TaskExecution.profile_name == profile_name
            )
            
            if not include_missed:
                query = query.filter(TaskExecution.missed == False)
            
            tasks = query.order_by(TaskExecution.scheduled_time.desc()).limit(limit).all()
            
            history = []
            for task in tasks:
                task_dict = {
                    "id": task.id,
                    "profile_name": task.profile_name,
                    "scheduled_time": task.scheduled_time.isoformat(),
                    "actual_start_time": task.actual_start_time.isoformat() if task.actual_start_time else None,
                    "completion_time": task.completion_time.isoformat() if task.completion_time else None,
                    "success": task.success,
                    "missed": task.missed,
                    "error_message": task.error_message,
                    "orders_processed": task.orders_processed,
                    "duration_seconds": task.duration_seconds,
                    "task_type": task.task_type,
                    "created_at": task.created_at.isoformat()
                }
                
                # Parse metadata if available
                if task.metadata_json:
                    try:
                        metadata = json.loads(task.metadata_json)
                        task_dict.update(metadata)
                    except json.JSONDecodeError:
                        pass
                
                history.append(task_dict)
            
            return history
            
        except Exception as e:
            logger.error(f"Error getting task history: {e}")
            return []
        finally:
            db.close()
    
    def get_missed_tasks(self, profile_name: str, hours_back: int = 24) -> List[Dict]:
        """Get missed tasks within a time window"""
        db = self.SessionLocal()
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours_back)
            
            missed_tasks = db.query(TaskExecution).filter(
                TaskExecution.profile_name == profile_name,
                TaskExecution.missed == True,
                TaskExecution.scheduled_time >= cutoff_time
            ).order_by(TaskExecution.scheduled_time.desc()).all()
            
            return [
                {
                    "id": task.id,
                    "scheduled_time": task.scheduled_time.isoformat(),
                    "error_message": task.error_message,
                    "task_type": task.task_type
                }
                for task in missed_tasks
            ]
            
        except Exception as e:
            logger.error(f"Error getting missed tasks: {e}")
            return []
        finally:
            db.close()
    
    def get_task_statistics(self, profile_name: str, hours_back: int = 24) -> Dict:
        """Get task execution statistics for a profile"""
        db = self.SessionLocal()
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours_back)
            
            # Get all tasks in the time window
            tasks = db.query(TaskExecution).filter(
                TaskExecution.profile_name == profile_name,
                TaskExecution.scheduled_time >= cutoff_time
            ).all()
            
            total_tasks = len(tasks)
            successful_tasks = len([t for t in tasks if t.success and not t.missed])
            failed_tasks = len([t for t in tasks if not t.success and not t.missed])
            missed_tasks = len([t for t in tasks if t.missed])
            
            # Calculate average duration for successful tasks
            successful_durations = [t.duration_seconds for t in tasks 
                                  if t.success and t.duration_seconds is not None]
            avg_duration = sum(successful_durations) / len(successful_durations) if successful_durations else 0
            
            # Get last successful task
            last_successful = db.query(TaskExecution).filter(
                TaskExecution.profile_name == profile_name,
                TaskExecution.success == True,
                TaskExecution.missed == False
            ).order_by(TaskExecution.completion_time.desc()).first()
            
            return {
                "profile_name": profile_name,
                "time_window_hours": hours_back,
                "total_tasks": total_tasks,
                "successful_tasks": successful_tasks,
                "failed_tasks": failed_tasks,
                "missed_tasks": missed_tasks,
                "success_rate": (successful_tasks / total_tasks * 100) if total_tasks > 0 else 0,
                "average_duration_seconds": round(avg_duration, 2),
                "last_successful_task": last_successful.completion_time.isoformat() if last_successful else None,
                "is_healthy": missed_tasks == 0 and failed_tasks < successful_tasks
            }
            
        except Exception as e:
            logger.error(f"Error getting task statistics: {e}")
            return {
                "profile_name": profile_name,
                "error": str(e)
            }
        finally:
            db.close()
    
    def cleanup_old_tasks(self, days_to_keep: int = 30) -> int:
        """Clean up old task execution records"""
        db = self.SessionLocal()
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            deleted_count = db.query(TaskExecution).filter(
                TaskExecution.created_at < cutoff_date
            ).delete()
            
            db.commit()
            logger.info(f"Cleaned up {deleted_count} old task execution records")
            return deleted_count
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error cleaning up old tasks: {e}")
            return 0
        finally:
            db.close()
    
    def get_system_health_summary(self) -> Dict:
        """Get overall system health summary"""
        db = self.SessionLocal()
        try:
            # Get all profiles that have task executions
            profiles = db.query(TaskExecution.profile_name).distinct().all()
            profile_names = [p[0] for p in profiles]
            
            system_summary = {
                "total_profiles": len(profile_names),
                "profiles": {},
                "overall_health": True
            }
            
            for profile_name in profile_names:
                profile_stats = self.get_task_statistics(profile_name, hours_back=24)
                system_summary["profiles"][profile_name] = profile_stats
                
                # Update overall health
                if not profile_stats.get("is_healthy", False):
                    system_summary["overall_health"] = False
            
            return system_summary
            
        except Exception as e:
            logger.error(f"Error getting system health summary: {e}")
            return {"error": str(e)}
        finally:
            db.close()
    
    def find_recovery_candidates(self, profile_name: str, max_gap_minutes: int = 15) -> List[Dict]:
        """Find tasks that might need recovery due to gaps in execution"""
        db = self.SessionLocal()
        try:
            # Get recent successful tasks
            recent_tasks = db.query(TaskExecution).filter(
                TaskExecution.profile_name == profile_name,
                TaskExecution.success == True,
                TaskExecution.missed == False,
                TaskExecution.completion_time >= datetime.now() - timedelta(hours=2)
            ).order_by(TaskExecution.completion_time.desc()).limit(10).all()
            
            recovery_candidates = []
            
            for i in range(len(recent_tasks) - 1):
                current_task = recent_tasks[i]
                next_task = recent_tasks[i + 1]
                
                # Calculate gap between tasks
                gap_minutes = (current_task.completion_time - next_task.completion_time).total_seconds() / 60
                
                if gap_minutes > max_gap_minutes:
                    recovery_candidates.append({
                        "gap_start": next_task.completion_time.isoformat(),
                        "gap_end": current_task.scheduled_time.isoformat(),
                        "gap_minutes": round(gap_minutes, 2),
                        "estimated_missed_tasks": int(gap_minutes / 5),  # Assuming 5-minute intervals
                        "priority": "high" if gap_minutes > 30 else "medium"
                    })
            
            return recovery_candidates
            
        except Exception as e:
            logger.error(f"Error finding recovery candidates: {e}")
            return []
        finally:
            db.close()

# Global task persistence manager instance
task_persistence_manager = TaskPersistenceManager()

def save_task_execution(task_data: Dict) -> Optional[int]:
    """Convenience function to save task execution"""
    return task_persistence_manager.save_task_execution(task_data)

def get_task_history(profile_name: str, limit: int = 50) -> List[Dict]:
    """Convenience function to get task history"""
    return task_persistence_manager.get_task_history(profile_name, limit)

def get_task_statistics(profile_name: str, hours_back: int = 24) -> Dict:
    """Convenience function to get task statistics"""
    return task_persistence_manager.get_task_statistics(profile_name, hours_back)

def cleanup_old_tasks(days_to_keep: int = 30) -> int:
    """Convenience function to cleanup old tasks"""
    return task_persistence_manager.cleanup_old_tasks(days_to_keep)
