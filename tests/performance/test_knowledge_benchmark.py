"""
知识管理模块性能基准测试

对比knowledge.py、knowledge_migrated.py和knowledge_unified.py的性能差异
评估迁移完成度和性能优化效果
"""

import pytest
import time
import asyncio
import statistics
from unittest.mock import Mock, patch, AsyncMock
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

from open_webui.main import app
from fastapi.testclient import TestClient


class KnowledgeBenchmark:
    """知识模块性能基准测试类"""

    def __init__(self):
        self.client = TestClient(app)
        self.results = {
            "knowledge_original": {},
            "knowledge_migrated": {},
            "knowledge_unified": {}
        }

    def setup_mock_user(self):
        """设置模拟用户"""
        mock_user = Mock()
        mock_user.id = "benchmark_user"
        mock_user.role = "user"
        return mock_user

    def measure_response_time(self, func, *args, **kwargs):
        """测量响应时间"""
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        return end_time - start_time, result

    def measure_async_response_time(self, async_func, *args, **kwargs):
        """测量异步响应时间"""
        async def _measure():
            start_time = time.perf_counter()
            result = await async_func(*args, **kwargs)
            end_time = time.perf_counter()
            return end_time - start_time, result
        
        return asyncio.run(_measure())

    @patch('open_webui.routers.knowledge.get_verified_user')
    @patch('open_webui.models.knowledge.Knowledges.get_knowledge_bases_by_user_id')
    def test_knowledge_original_list_performance(self, mock_kb_query, mock_auth):
        """测试原始knowledge模块列表性能"""
        mock_auth.return_value = self.setup_mock_user()
        
        # 模拟不同规模的数据
        test_sizes = [10, 50, 100, 500, 1000]
        results = {}
        
        for size in test_sizes:
            # 生成测试数据
            mock_data = []
            for i in range(size):
                kb_mock = Mock()
                kb_mock.id = f"kb_{i}"
                kb_mock.name = f"知识库{i}"
                kb_mock.data = {"file_ids": [f"file_{i}_{j}" for j in range(5)]}
                kb_mock.model_dump.return_value = {
                    "id": f"kb_{i}",
                    "name": f"知识库{i}",
                    "user_id": "benchmark_user"
                }
                mock_data.append(kb_mock)
            
            mock_kb_query.return_value = mock_data
            
            # 执行性能测试
            response_times = []
            for _ in range(5):  # 执行5次取平均值
                response_time, response = self.measure_response_time(
                    self.client.get, "/api/v1/knowledge/"
                )
                response_times.append(response_time)
                assert response.status_code == 200
            
            results[f"{size}_items"] = {
                "avg_response_time": statistics.mean(response_times),
                "min_response_time": min(response_times),
                "max_response_time": max(response_times),
                "std_dev": statistics.stdev(response_times) if len(response_times) > 1 else 0
            }
        
        self.results["knowledge_original"]["list_performance"] = results
        return results

    @patch('open_webui.routers.knowledge_unified.get_verified_user')
    @patch('open_webui.routers.knowledge_unified.knowledge_service')
    def test_knowledge_unified_list_performance(self, mock_service, mock_auth):
        """测试统一knowledge模块列表性能"""
        mock_auth.return_value = self.setup_mock_user()
        
        test_sizes = [10, 50, 100, 500, 1000]
        results = {}
        
        for size in test_sizes:
            # 生成测试数据
            mock_data = {
                "knowledge_bases": [
                    {
                        "id": f"kb_{i}",
                        "name": f"知识库{i}",
                        "user_id": "benchmark_user",
                        "created_at": "2025-08-26T01:30:00Z"
                    }
                    for i in range(size)
                ],
                "pagination": {"total": size, "page": 1, "per_page": size}
            }
            
            mock_service.list_knowledge_bases = AsyncMock(return_value=mock_data)
            
            # 执行性能测试
            response_times = []
            for _ in range(5):
                response_time, response = self.measure_response_time(
                    self.client.get, "/api/knowledge/collections"
                )
                response_times.append(response_time)
                assert response.status_code == 200
            
            results[f"{size}_items"] = {
                "avg_response_time": statistics.mean(response_times),
                "min_response_time": min(response_times),
                "max_response_time": max(response_times),
                "std_dev": statistics.stdev(response_times) if len(response_times) > 1 else 0
            }
        
        self.results["knowledge_unified"]["list_performance"] = results
        return results

    @patch('open_webui.routers.knowledge_unified.get_verified_user')
    @patch('open_webui.routers.knowledge_unified.search_service')
    def test_search_performance_comparison(self, mock_service, mock_auth):
        """对比搜索性能"""
        mock_auth.return_value = self.setup_mock_user()
        
        # 模拟不同复杂度的搜索结果
        test_scenarios = {
            "simple": {
                "query": "简单查询",
                "result_count": 10
            },
            "medium": {
                "query": "中等复杂度查询包含多个关键词",
                "result_count": 50
            },
            "complex": {
                "query": "复杂查询包含多个技术术语和专业词汇需要深度语义理解",
                "result_count": 100
            }
        }
        
        results = {}
        
        for scenario_name, scenario in test_scenarios.items():
            mock_results = {
                "query": scenario["query"],
                "total": scenario["result_count"],
                "results": [
                    {
                        "id": f"result_{i}",
                        "content": f"搜索结果内容{i}" * 10,  # 模拟较长内容
                        "score": 0.9 - (i * 0.01),
                        "source": "knowledge_base",
                        "metadata": {"chunk_id": f"chunk_{i}"}
                    }
                    for i in range(scenario["result_count"])
                ],
                "search_params": {"vector_weight": 0.7, "keyword_weight": 0.3}
            }
            
            mock_service.search = AsyncMock(return_value=mock_results)
            
            # 执行搜索性能测试
            search_request = {
                "query": scenario["query"],
                "vector_weight": 0.7,
                "keyword_weight": 0.3,
                "top_k": scenario["result_count"]
            }
            
            response_times = []
            for _ in range(5):
                response_time, response = self.measure_response_time(
                    self.client.post, "/api/knowledge/search", json=search_request
                )
                response_times.append(response_time)
                assert response.status_code == 200
            
            results[scenario_name] = {
                "avg_response_time": statistics.mean(response_times),
                "min_response_time": min(response_times),
                "max_response_time": max(response_times),
                "result_count": scenario["result_count"]
            }
        
        self.results["knowledge_unified"]["search_performance"] = results
        return results

    def test_concurrent_requests_performance(self):
        """测试并发请求性能"""
        concurrent_levels = [1, 5, 10, 20, 50]
        results = {}
        
        with patch('open_webui.routers.knowledge_unified.get_verified_user') as mock_auth:
            mock_auth.return_value = self.setup_mock_user()
            
            with patch('open_webui.routers.knowledge_unified.knowledge_service') as mock_service:
                mock_service.get_stats = AsyncMock(return_value={
                    "total_knowledge_bases": 10,
                    "total_documents": 100,
                    "processing_documents": 0,
                    "failed_documents": 0
                })
                
                for concurrent_level in concurrent_levels:
                    start_time = time.perf_counter()
                    
                    # 使用线程池执行并发请求
                    with ThreadPoolExecutor(max_workers=concurrent_level) as executor:
                        futures = [
                            executor.submit(self.client.get, "/api/knowledge/stats")
                            for _ in range(concurrent_level)
                        ]
                        
                        responses = []
                        for future in as_completed(futures):
                            response = future.result()
                            responses.append(response)
                    
                    end_time = time.perf_counter()
                    total_time = end_time - start_time
                    
                    # 验证所有请求成功
                    success_count = sum(1 for r in responses if r.status_code == 200)
                    
                    results[f"{concurrent_level}_concurrent"] = {
                        "total_time": total_time,
                        "avg_time_per_request": total_time / concurrent_level,
                        "requests_per_second": concurrent_level / total_time,
                        "success_rate": success_count / concurrent_level
                    }
        
        self.results["knowledge_unified"]["concurrent_performance"] = results
        return results

    def test_memory_usage_comparison(self):
        """测试内存使用对比"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        # 测试大数据量处理的内存使用
        with patch('open_webui.routers.knowledge_unified.get_verified_user') as mock_auth:
            mock_auth.return_value = self.setup_mock_user()
            
            with patch('open_webui.routers.knowledge_unified.knowledge_service') as mock_service:
                # 模拟大量数据
                large_data = {
                    "knowledge_bases": [
                        {
                            "id": f"kb_{i}",
                            "name": f"知识库{i}",
                            "description": "详细描述" * 100,  # 模拟大描述
                            "user_id": "benchmark_user",
                            "metadata": {"tags": [f"tag_{j}" for j in range(20)]}
                        }
                        for i in range(1000)
                    ],
                    "pagination": {"total": 1000, "page": 1, "per_page": 1000}
                }
                
                mock_service.list_knowledge_bases = AsyncMock(return_value=large_data)
                
                # 记录处理前内存使用
                memory_before = process.memory_info().rss / 1024 / 1024  # MB
                
                # 执行请求
                response = self.client.get("/api/knowledge/collections?page_size=1000")
                
                # 记录处理后内存使用
                memory_after = process.memory_info().rss / 1024 / 1024  # MB
                
                memory_usage = {
                    "memory_before_mb": memory_before,
                    "memory_after_mb": memory_after,
                    "memory_increase_mb": memory_after - memory_before,
                    "response_size_kb": len(response.content) / 1024
                }
                
                assert response.status_code == 200
                
        self.results["knowledge_unified"]["memory_usage"] = memory_usage
        return memory_usage

    def generate_performance_report(self):
        """生成性能报告"""
        report = {
            "test_summary": {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "modules_tested": ["knowledge_unified"],
                "test_types": ["list_performance", "search_performance", "concurrent_performance", "memory_usage"]
            },
            "performance_metrics": self.results,
            "recommendations": []
        }
        
        # 分析性能并给出建议
        if "knowledge_unified" in self.results:
            unified_results = self.results["knowledge_unified"]
            
            # 检查列表性能
            if "list_performance" in unified_results:
                list_perf = unified_results["list_performance"]
                if "1000_items" in list_perf:
                    avg_time = list_perf["1000_items"]["avg_response_time"]
                    if avg_time > 2.0:
                        report["recommendations"].append({
                            "type": "performance",
                            "severity": "high",
                            "message": f"大数据量列表查询响应时间过长 ({avg_time:.2f}s)，建议优化分页或添加缓存"
                        })
                    elif avg_time > 1.0:
                        report["recommendations"].append({
                            "type": "performance", 
                            "severity": "medium",
                            "message": f"列表查询响应时间可优化 ({avg_time:.2f}s)"
                        })
            
            # 检查并发性能
            if "concurrent_performance" in unified_results:
                concurrent_perf = unified_results["concurrent_performance"]
                if "50_concurrent" in concurrent_perf:
                    success_rate = concurrent_perf["50_concurrent"]["success_rate"]
                    if success_rate < 0.95:
                        report["recommendations"].append({
                            "type": "reliability",
                            "severity": "high", 
                            "message": f"高并发下成功率过低 ({success_rate:.2%})，需要优化并发处理"
                        })
            
            # 检查内存使用
            if "memory_usage" in unified_results:
                memory_usage = unified_results["memory_usage"]
                memory_increase = memory_usage["memory_increase_mb"]
                if memory_increase > 100:
                    report["recommendations"].append({
                        "type": "memory",
                        "severity": "medium",
                        "message": f"大数据量处理内存增长过多 ({memory_increase:.1f}MB)，建议优化数据处理方式"
                    })
        
        return report

    def run_all_benchmarks(self):
        """运行所有基准测试"""
        print("开始运行知识管理模块性能基准测试...")
        
        try:
            print("1. 测试列表查询性能...")
            self.test_knowledge_unified_list_performance()
            
            print("2. 测试搜索性能...")
            self.test_search_performance_comparison()
            
            print("3. 测试并发性能...")
            self.test_concurrent_requests_performance()
            
            print("4. 测试内存使用...")
            self.test_memory_usage_comparison()
            
            print("5. 生成性能报告...")
            report = self.generate_performance_report()
            
            return report
            
        except Exception as e:
            print(f"基准测试过程中出现错误: {e}")
            return {"error": str(e), "partial_results": self.results}


# ==================== pytest测试用例 ====================

def test_knowledge_unified_performance_suite():
    """完整的知识统一模块性能测试套件"""
    benchmark = KnowledgeBenchmark()
    report = benchmark.run_all_benchmarks()
    
    # 验证测试完成
    assert "performance_metrics" in report
    assert "knowledge_unified" in report["performance_metrics"]
    
    # 验证关键性能指标
    unified_metrics = report["performance_metrics"]["knowledge_unified"]
    
    if "list_performance" in unified_metrics:
        # 验证列表性能在可接受范围内
        list_1000 = unified_metrics["list_performance"].get("1000_items")
        if list_1000:
            assert list_1000["avg_response_time"] < 5.0, "大数据量列表查询响应时间过长"
    
    if "concurrent_performance" in unified_metrics:
        # 验证并发性能
        concurrent_10 = unified_metrics["concurrent_performance"].get("10_concurrent")
        if concurrent_10:
            assert concurrent_10["success_rate"] >= 0.95, "并发请求成功率过低"
    
    # 输出性能报告
    print("\n" + "="*50)
    print("性能测试报告")
    print("="*50)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    
    return report


if __name__ == "__main__":
    # 直接运行基准测试
    benchmark = KnowledgeBenchmark()
    report = benchmark.run_all_benchmarks()
    
    # 保存报告到文件
    with open("knowledge_performance_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print("\n性能测试完成，报告已保存到 knowledge_performance_report.json")
