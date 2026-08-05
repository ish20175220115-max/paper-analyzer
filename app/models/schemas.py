from pydantic import BaseModel, Field
from datetime import datetime


class DimensionSpec(BaseModel):
    """分析维度规格 —— 预置或用户编辑后统一为此格式"""
    label: str = Field(..., min_length=1, max_length=30, description="维度名称")
    description: str = Field(default="", max_length=1500, description="分析要求说明")


class AnalyzeRequest(BaseModel):
    """分析请求"""
    content: str = Field(..., min_length=1, description="论文 markdown 内容")
    dimensions: list[DimensionSpec] = Field(..., min_length=1, description="分析维度列表")


class ReportSection(BaseModel):
    """报告的单个分析段落"""
    dimension: str
    content: str


class SaveReportRequest(BaseModel):
    """保存报告请求"""
    paper_title: str
    original_content: str
    sections: list[ReportSection]
    dimensions: list[str]  # 维度标签列表


class ReportSummary(BaseModel):
    """报告列表摘要"""
    id: str
    paper_title: str
    dimensions: list[str]
    created_at: str


class ReportDetail(BaseModel):
    """报告详情"""
    id: str
    paper_title: str
    sections: list[ReportSection]
    original_content: str
    created_at: str
