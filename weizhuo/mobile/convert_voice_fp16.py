"""FP16 weight storage with FP32 graph/IO for the existing CPU provider.

Requires onnx and numpy on the development computer, not in the App.
The runtime may fold Cast nodes back to FP32: reduced disk size is not a
claim of FP16 arithmetic, lower resident memory, or faster inference.
"""
from pathlib import Path
import argparse
import onnx
import numpy as np
from onnx import numpy_helper,helper,TensorProto

def convert(source,destination):
    model=onnx.load(source)
    nodes=[];converted=0
    # Integer tensors and the graph's operator and IO types stay unchanged.
    names={x.name for x in model.graph.initializer}
    for tensor in model.graph.initializer:
        if tensor.data_type!=TensorProto.FLOAT:continue
        values=numpy_helper.to_array(tensor)
        if not np.isfinite(values).all() or np.max(np.abs(values),initial=0)>np.finfo(np.float16).max:
            continue
        original=tensor.name;stored=original+'__wz_fp16'
        if stored in names:raise ValueError('Initializer name collision')
        tensor.CopyFrom(numpy_helper.from_array(values.astype(np.float16),stored))
        nodes.append(helper.make_node('Cast',[stored],[original],name=stored+'__to_fp32',to=TensorProto.FLOAT))
        converted+=1
    nodes.extend(model.graph.node);del model.graph.node[:];model.graph.node.extend(nodes)
    onnx.checker.check_model(model)
    onnx.save(model,destination)
    print(f'{converted} FP16 weight tensors; {Path(source).stat().st_size/2**20:.2f} → {Path(destination).stat().st_size/2**20:.2f} MiB')
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);parser.add_argument('destination',type=Path)
    args=parser.parse_args();convert(args.source,args.destination)
