# Copyright (c) 2026 OceanBase.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#!/usr/bin/env python3
"""
量化产生方式(可复现脚本)

本项目默认直接使用 Xenova 官方导出的三份 ONNX 权重:
    onnx/model.onnx            FP32 基线
    onnx/model_fp16.onnx       FP16
    onnx/model_quantized.onnx  INT8(动态量化)

这个脚本用于「自己从 FP32 复现出 FP16 / INT8 权重」,方便评委核对量化是怎么来的:

    # 1) 装依赖(国内可用清华镜像)
    pip install -i https://pypi.tuna.tsinghua.edu.cn/simple onnx onnxruntime onnxconverter-common

    # 2) 先把 FP32 权重准备好
    npm run model:fetch        # 或手动下载 Xenova/all-MiniLM-L6-v2 的 onnx/model.onnx

    # 3) 生成量化权重
    python scripts/quantize_model.py \
        --fp32 web/public/models/Xenova/all-MiniLM-L6-v2/onnx/model.onnx \
        --outdir web/public/models/Xenova/all-MiniLM-L6-v2/onnx

INT8  = onnxruntime.quantization.quantize_dynamic(per_channel=False, reduce_range=False)
        —— 权重 int8(MatMulInteger / DynamicQuantizeLinear),激活值运行时动态量化
FP16  = onnxconverter_common.float16.convert_float_to_float_float16(keep_io_types=True)
        —— 权重与计算转 FP16,输入输出仍保持 FP32

脚本会打印生成文件与官方文件的大小/sha256 对比,便于确认是否一致。
"""
import argparse
import hashlib
import os
import shutil
import sys


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def human(n: int) -> str:
    return f"{n / 1048576:.1f} MB"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fp32", required=True, help="FP32 onnx 权重路径")
    ap.add_argument("--outdir", required=True, help="输出目录")
    ap.add_argument("--skip-fp16", action="store_true")
    ap.add_argument("--skip-int8", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    # ---------- INT8:动态量化 ----------
    if not args.skip_int8:
        from onnxruntime.quantization import QuantType, quantize_dynamic

        out_int8 = os.path.join(args.outdir, "model_quantized.repro.onnx")
        print(f"[int8] {args.fp32} -> {out_int8}")
        quantize_dynamic(
            model_input=args.fp32,
            model_output=out_int8,
            weight_type=QuantType.QInt8,
            per_channel=False,
            reduce_range=False,
        )

    # ---------- FP16:权重转半精度 ----------
    if not args.skip_fp16:
        import onnx
        from onnxconverter_common import float16

        out_fp16 = os.path.join(args.outdir, "model_fp16.repro.onnx")
        print(f"[fp16] {args.fp32} -> {out_fp16}")
        model = onnx.load(args.fp32)
        model_fp16 = float16.convert_float_to_float16(model, keep_io_types=True)
        onnx.save(model_fp16, out_fp16)

    # ---------- 对比官方文件 ----------
    # 官方权重与 FP32 基线放在同一个目录里(就是模型目录)
    official_dir = os.path.dirname(os.path.abspath(args.fp32))
    print("\n%-38s %12s %12s %18s %18s" % ("文件", "本地产出", "官方文件", "本地 sha256", "官方 sha256"))
    pairs = [
        ("model_quantized.repro.onnx", "model_quantized.onnx"),
        ("model_fp16.repro.onnx", "model_fp16.onnx"),
    ]
    for local_name, official_name in pairs:
        local = os.path.join(args.outdir, local_name)
        official = os.path.join(official_dir, official_name)
        if not os.path.exists(local):
            continue
        ls, os_ = os.path.getsize(local), (os.path.getsize(official) if os.path.exists(official) else 0)
        print(
            "%-38s %12s %12s %18s %18s"
            % (
                local_name,
                human(ls),
                human(os_) if os_ else "-",
                sha256(local)[:16],
                sha256(official)[:16] if os_ else "-",
            )
        )
        if os_:
            ratio = ls / os_ if os_ else 0
            print(f"    体积比(本地/官方) = {ratio:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
