import PDFKit
import Foundation
let a = CommandLine.arguments
if let d = PDFDocument(url: URL(fileURLWithPath: a[1])) { print(d.string ?? "") }
