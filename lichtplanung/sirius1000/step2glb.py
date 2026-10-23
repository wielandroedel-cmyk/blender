"""Convert a STEP assembly to binary glTF, keeping names, colors and transparency."""
import sys

from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.IFSelect import IFSelect_RetDone
from OCP.Message import Message_ProgressRange
from OCP.RWGltf import RWGltf_CafWriter
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.collections import IndexedDataMap_TCollection_AsciiString_TCollection_AsciiString as FileInfoMap
from OCP.TCollection import TCollection_AsciiString, TCollection_ExtendedString
from OCP.collections import Sequence_TDF_Label as TDF_LabelSequence
from OCP.TDocStd import TDocStd_Document
from OCP.XCAFDoc import XCAFDoc_DocumentTool

src, dst = sys.argv[1], sys.argv[2]
doc = TDocStd_Document(TCollection_ExtendedString("XmlOcaf"))
reader = STEPCAFControl_Reader()
reader.SetColorMode(True)
reader.SetNameMode(True)
reader.SetLayerMode(True)
if reader.ReadFile(src) != IFSelect_RetDone:
    sys.exit("Failed to read STEP file")
reader.Transfer(doc)

shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
labels = TDF_LabelSequence()
shape_tool.GetFreeShapes(labels)
for i in range(1, labels.Length() + 1):
    shape = shape_tool.GetShape_s(labels.Value(i))
    # Linear deflection in model units (mm), angular deflection in radians.
    BRepMesh_IncrementalMesh(shape, 0.3, False, 0.2, True)

writer = RWGltf_CafWriter(TCollection_AsciiString(dst), True)
writer.Perform(doc, FileInfoMap(), Message_ProgressRange())
print("written", dst)
