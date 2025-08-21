"""
文件安全扫描服务

提供文件安全检查功能，包括：
1. 病毒扫描
2. 恶意代码检测
3. 文件类型验证
4. 内容安全检查
"""

import os
import hashlib
import mimetypes
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import magic
import yara
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class ScanResult(BaseModel):
    """扫描结果模型"""
    is_safe: bool
    risk_level: str  # "low", "medium", "high"
    threats: List[str]
    file_type: str
    file_size: int
    md5_hash: str
    scan_time: float
    details: Dict

class SecurityScanner:
    """文件安全扫描器"""
    
    def __init__(self):
        self.allowed_extensions = {
            '.pdf', '.doc', '.docx', '.txt', '.md', '.rtf',
            '.xls', '.xlsx', '.csv', '.ppt', '.pptx',
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
            '.zip', '.rar', '.7z', '.tar', '.gz'
        }
        
        self.dangerous_extensions = {
            '.exe', '.bat', '.cmd', '.com', '.scr', '.pif',
            '.vbs', '.js', '.jar', '.app', '.deb', '.rpm',
            '.msi', '.dmg', '.pkg', '.sh', '.ps1'
        }
        
        self.max_file_size = 100 * 1024 * 1024  # 100MB
        
        # 初始化YARA规则（如果可用）
        self.yara_rules = self._load_yara_rules()
    
    def _load_yara_rules(self) -> Optional[yara.Rules]:
        """加载YARA恶意代码检测规则"""
        try:
            rules_path = Path(__file__).parent / "yara_rules"
            if rules_path.exists():
                rule_files = list(rules_path.glob("*.yar"))
                if rule_files:
                    return yara.compile(filepaths={
                        f.stem: str(f) for f in rule_files
                    })
        except Exception as e:
            logger.warning(f"无法加载YARA规则: {e}")
        return None
    
    def scan_file(self, file_path: str, filename: str = None) -> ScanResult:
        """
        扫描文件安全性
        
        Args:
            file_path: 文件路径
            filename: 原始文件名（可选）
            
        Returns:
            ScanResult: 扫描结果
        """
        import time
        start_time = time.time()
        
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"文件不存在: {file_path}")
            
            filename = filename or file_path.name
            file_size = file_path.stat().st_size
            
            # 计算文件哈希
            md5_hash = self._calculate_md5(file_path)
            
            # 检查文件大小
            size_check = self._check_file_size(file_size)
            
            # 检查文件扩展名
            extension_check = self._check_file_extension(filename)
            
            # 检查文件类型（MIME类型）
            mime_check = self._check_mime_type(file_path)
            
            # 检查文件内容
            content_check = self._check_file_content(file_path)
            
            # YARA规则扫描（如果可用）
            yara_check = self._yara_scan(file_path)
            
            # 综合评估
            threats = []
            risk_level = "low"
            is_safe = True
            
            # 收集威胁信息
            for check_name, check_result in [
                ("size", size_check),
                ("extension", extension_check),
                ("mime", mime_check),
                ("content", content_check),
                ("yara", yara_check)
            ]:
                if not check_result["safe"]:
                    threats.extend(check_result["threats"])
                    if check_result["risk_level"] == "high":
                        risk_level = "high"
                        is_safe = False
                    elif check_result["risk_level"] == "medium" and risk_level == "low":
                        risk_level = "medium"
                        if check_name in ["extension", "yara"]:
                            is_safe = False
            
            scan_time = time.time() - start_time
            
            return ScanResult(
                is_safe=is_safe,
                risk_level=risk_level,
                threats=threats,
                file_type=mime_check["mime_type"],
                file_size=file_size,
                md5_hash=md5_hash,
                scan_time=scan_time,
                details={
                    "size_check": size_check,
                    "extension_check": extension_check,
                    "mime_check": mime_check,
                    "content_check": content_check,
                    "yara_check": yara_check
                }
            )
            
        except Exception as e:
            logger.error(f"文件扫描失败: {e}")
            return ScanResult(
                is_safe=False,
                risk_level="high",
                threats=[f"扫描失败: {str(e)}"],
                file_type="unknown",
                file_size=0,
                md5_hash="",
                scan_time=time.time() - start_time,
                details={"error": str(e)}
            )
    
    def _calculate_md5(self, file_path: Path) -> str:
        """计算文件MD5哈希"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def _check_file_size(self, file_size: int) -> Dict:
        """检查文件大小"""
        if file_size > self.max_file_size:
            return {
                "safe": False,
                "risk_level": "medium",
                "threats": [f"文件过大: {file_size / 1024 / 1024:.1f}MB > {self.max_file_size / 1024 / 1024}MB"]
            }
        
        return {
            "safe": True,
            "risk_level": "low",
            "threats": []
        }
    
    def _check_file_extension(self, filename: str) -> Dict:
        """检查文件扩展名"""
        ext = Path(filename).suffix.lower()
        
        if ext in self.dangerous_extensions:
            return {
                "safe": False,
                "risk_level": "high",
                "threats": [f"危险文件类型: {ext}"]
            }
        
        if ext not in self.allowed_extensions:
            return {
                "safe": False,
                "risk_level": "medium",
                "threats": [f"不支持的文件类型: {ext}"]
            }
        
        return {
            "safe": True,
            "risk_level": "low",
            "threats": []
        }
    
    def _check_mime_type(self, file_path: Path) -> Dict:
        """检查MIME类型"""
        try:
            # 使用python-magic检测真实文件类型
            mime_type = magic.from_file(str(file_path), mime=True)
            
            # 检查是否为允许的MIME类型
            allowed_mime_types = {
                'application/pdf',
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'text/plain',
                'text/markdown',
                'application/rtf',
                'application/vnd.ms-excel',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'text/csv',
                'application/vnd.ms-powerpoint',
                'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                'image/jpeg',
                'image/png',
                'image/gif',
                'image/bmp',
                'image/webp',
                'application/zip',
                'application/x-rar-compressed',
                'application/x-7z-compressed',
                'application/x-tar',
                'application/gzip'
            }
            
            dangerous_mime_types = {
                'application/x-executable',
                'application/x-msdos-program',
                'application/x-msdownload',
                'application/x-dosexec'
            }
            
            if mime_type in dangerous_mime_types:
                return {
                    "safe": False,
                    "risk_level": "high",
                    "threats": [f"危险MIME类型: {mime_type}"],
                    "mime_type": mime_type
                }
            
            if mime_type not in allowed_mime_types:
                return {
                    "safe": False,
                    "risk_level": "medium",
                    "threats": [f"不支持的MIME类型: {mime_type}"],
                    "mime_type": mime_type
                }
            
            return {
                "safe": True,
                "risk_level": "low",
                "threats": [],
                "mime_type": mime_type
            }
            
        except Exception as e:
            logger.warning(f"MIME类型检测失败: {e}")
            return {
                "safe": False,
                "risk_level": "medium",
                "threats": [f"MIME类型检测失败: {str(e)}"],
                "mime_type": "unknown"
            }
    
    def _check_file_content(self, file_path: Path) -> Dict:
        """检查文件内容"""
        threats = []
        risk_level = "low"
        
        try:
            # 检查文件头部特征
            with open(file_path, 'rb') as f:
                header = f.read(1024)
            
            # 检查可执行文件特征
            executable_signatures = [
                b'MZ',  # PE executable
                b'\x7fELF',  # ELF executable
                b'\xfe\xed\xfa',  # Mach-O executable
                b'\xcf\xfa\xed\xfe',  # Mach-O executable
            ]
            
            for sig in executable_signatures:
                if header.startswith(sig):
                    threats.append("检测到可执行文件特征")
                    risk_level = "high"
                    break
            
            # 检查脚本内容（对于文本文件）
            if self._is_text_file(file_path):
                text_threats = self._check_text_content(file_path)
                threats.extend(text_threats)
                if text_threats:
                    risk_level = "medium"
            
            return {
                "safe": len(threats) == 0,
                "risk_level": risk_level,
                "threats": threats
            }
            
        except Exception as e:
            logger.warning(f"文件内容检查失败: {e}")
            return {
                "safe": True,
                "risk_level": "low",
                "threats": []
            }
    
    def _is_text_file(self, file_path: Path) -> bool:
        """判断是否为文本文件"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                f.read(1024)
            return True
        except:
            return False
    
    def _check_text_content(self, file_path: Path) -> List[str]:
        """检查文本文件内容"""
        threats = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(10240)  # 只读取前10KB
            
            # 检查可疑脚本内容
            suspicious_patterns = [
                'eval(',
                'exec(',
                'system(',
                'shell_exec(',
                'passthru(',
                'base64_decode(',
                'javascript:',
                'vbscript:',
                'powershell',
                'cmd.exe',
                '/bin/sh',
                'wget',
                'curl'
            ]
            
            content_lower = content.lower()
            for pattern in suspicious_patterns:
                if pattern in content_lower:
                    threats.append(f"检测到可疑代码模式: {pattern}")
            
        except Exception as e:
            logger.warning(f"文本内容检查失败: {e}")
        
        return threats
    
    def _yara_scan(self, file_path: Path) -> Dict:
        """YARA规则扫描"""
        if not self.yara_rules:
            return {
                "safe": True,
                "risk_level": "low",
                "threats": []
            }
        
        try:
            matches = self.yara_rules.match(str(file_path))
            
            if matches:
                threats = [f"YARA规则匹配: {match.rule}" for match in matches]
                return {
                    "safe": False,
                    "risk_level": "high",
                    "threats": threats
                }
            
            return {
                "safe": True,
                "risk_level": "low",
                "threats": []
            }
            
        except Exception as e:
            logger.warning(f"YARA扫描失败: {e}")
            return {
                "safe": True,
                "risk_level": "low",
                "threats": []
            }
    
    def scan_multiple_files(self, file_paths: List[str]) -> Dict[str, ScanResult]:
        """批量扫描多个文件"""
        results = {}
        
        for file_path in file_paths:
            try:
                results[file_path] = self.scan_file(file_path)
            except Exception as e:
                logger.error(f"扫描文件 {file_path} 失败: {e}")
                results[file_path] = ScanResult(
                    is_safe=False,
                    risk_level="high",
                    threats=[f"扫描失败: {str(e)}"],
                    file_type="unknown",
                    file_size=0,
                    md5_hash="",
                    scan_time=0,
                    details={"error": str(e)}
                )
        
        return results

# 全局扫描器实例
security_scanner = SecurityScanner()

def scan_file_security(file_path: str, filename: str = None) -> ScanResult:
    """扫描单个文件的安全性"""
    return security_scanner.scan_file(file_path, filename)

def scan_multiple_files_security(file_paths: List[str]) -> Dict[str, ScanResult]:
    """批量扫描文件安全性"""
    return security_scanner.scan_multiple_files(file_paths)
