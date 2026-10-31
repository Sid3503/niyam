import PDFKit
import Vision
import AppKit
import Foundation
let a = CommandLine.arguments
guard let d = PDFDocument(url: URL(fileURLWithPath: a[1])) else { exit(1) }
for i in 0..<d.pageCount {
  guard let p = d.page(at: i) else { continue }
  let r = p.bounds(for: .mediaBox)
  let s: CGFloat = 2.5
  let img = NSImage(size: NSSize(width: r.width*s, height: r.height*s))
  img.lockFocus(); NSColor.white.set(); NSRect(origin: .zero, size: img.size).fill()
  let ctx = NSGraphicsContext.current!.cgContext; ctx.scaleBy(x: s, y: s); p.draw(with: .mediaBox, to: ctx); img.unlockFocus()
  guard let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
  let req = VNRecognizeTextRequest(); req.recognitionLevel = .accurate; req.usesLanguageCorrection = true
  try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
  print("--- page \(i+1) ---")
  for o in req.results ?? [] { if let t = o.topCandidates(1).first { print(t.string) } }
}
