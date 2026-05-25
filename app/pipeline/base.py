
"""
Pipeline 基礎類別
定義所有管道階段的共通介面
"""
from abc import ABC, abstractmethod
import pandas as pd
import logging

class PipelineStage(ABC):
    """資料管道階段的抽象基底類別"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        
    @abstractmethod
    def execute(self, data: pd.DataFrame, context: dict) -> pd.DataFrame:
        """
        執行該管道階段的邏輯
        
        Args:
            data: 輸入的 DataFrame
            context: 用於跨階段共享資訊的上下文字典
            
        Returns:
            處理後的 DataFrame
        """
        pass
