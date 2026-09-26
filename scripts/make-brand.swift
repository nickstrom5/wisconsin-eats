// Regenerates the brand images: the app icon (a wedge of cheese), docs/brand/, and the site's og.png, favicons and manifest icons.
// Usage: swift scripts/make-brand.swift   (run from the repo root)
import AppKit
import CoreGraphics

let root = FileManager.default.currentDirectoryPath
let green = CGColor(srgbRed: 0x20 / 255, green: 0x37 / 255, blue: 0x31 / 255, alpha: 1)
let gold = CGColor(srgbRed: 1, green: 0xB6 / 255, blue: 0x12 / 255, alpha: 1)
let white = CGColor(srgbRed: 1, green: 1, blue: 1, alpha: 1)

func canvas(_ w: Int, _ h: Int, _ draw: (CGContext) -> Void) -> CGImage {
    let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
                        space: CGColorSpace(name: CGColorSpace.sRGB)!, bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
    draw(ctx)
    return ctx.makeImage()!
}

func save(_ img: CGImage, _ path: String) {
    let url = URL(fileURLWithPath: root + "/" + path)
    try? FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
    let rep = NSBitmapImageRep(cgImage: img)
    try! rep.representation(using: .png, properties: [:])!.write(to: url)
    print("wrote", path)
}

let goldTop = CGColor(srgbRed: 1, green: 0xD4 / 255, blue: 0x5E / 255, alpha: 1)
let goldSide = CGColor(srgbRed: 0xE0 / 255, green: 0x9A / 255, blue: 0x00, alpha: 1)

/// A wedge of cheese seen from the front: a lighter top face running back to a point, a gold front face
/// with holes, and a darker end. (x, y) is the bottom-left of the front face; `w` its width.
func cheese(_ c: CGContext, x: CGFloat, y: CGFloat, w: CGFloat, hole: CGColor) {
    let h = w * 0.40, back = w * 0.34, apex = CGPoint(x: x + w * 0.30, y: y + h + back)
    // top face
    let top = CGMutablePath()
    top.move(to: CGPoint(x: x, y: y + h)); top.addLine(to: CGPoint(x: x + w, y: y + h)); top.addLine(to: apex); top.closeSubpath()
    c.setFillColor(goldTop); c.addPath(top); c.fillPath()
    // front face, with holes cut into it (even-odd), a couple of them bitten into the edges
    let face = CGRect(x: x, y: y, width: w, height: h)
    c.saveGState()
    c.clip(to: face)
    c.setFillColor(gold); c.fill(face)
    c.setFillColor(hole)
    let holes: [(CGFloat, CGFloat, CGFloat)] = [(0.17, 0.52, 0.085), (0.46, 0.30, 0.06), (0.74, 0.60, 0.10), (0.58, 0.78, 0.045), (0.30, 0.18, 0.04), (1.0, 0.25, 0.07), (0.0, 0.85, 0.05)]
    for (hx, hy, r) in holes {
        c.fillEllipse(in: CGRect(x: x + w * hx - w * r, y: y + h * hy - w * r, width: w * r * 2, height: w * r * 2))
    }
    c.restoreGState()
    // a hole on the top face, squashed by perspective
    c.setFillColor(hole)
    c.fillEllipse(in: CGRect(x: x + w * 0.44, y: y + h + back * 0.30, width: w * 0.12, height: w * 0.05))
    // shading line where the faces meet
    c.setFillColor(goldSide)
    c.fill(CGRect(x: x, y: y + h - w * 0.012, width: w, height: w * 0.012))
}

func icon(_ size: Int) -> CGImage {
    canvas(size, size) { c in
        let s = CGFloat(size)
        c.setFillColor(green); c.fill(CGRect(x: 0, y: 0, width: s, height: s))
        cheese(c, x: s * 0.15, y: s * 0.26, w: s * 0.70, hole: green)
    }
}

func text(_ c: CGContext, _ str: String, font: NSFont, color: CGColor, at p: CGPoint) {
    let attr = NSAttributedString(string: str, attributes: [.font: font, .foregroundColor: NSColor(cgColor: color)!])
    let line = CTLineCreateWithAttributedString(attr)
    c.textPosition = p
    CTLineDraw(line, c)
}

func heavy(_ size: CGFloat) -> NSFont {
    NSFont(name: "HelveticaNeue-CondensedBlack", size: size) ?? NSFont.systemFont(ofSize: size, weight: .black)
}

let appIcon = icon(1024)
save(appIcon, "WisconsinEats/Resources/Assets.xcassets/AppIcon.appiconset/icon-1024.png")
save(appIcon, "docs/brand/icon-1024.png")
save(icon(512), "docs/icon-512.png")
save(icon(192), "docs/icon-192.png")
save(icon(180), "docs/apple-touch-icon.png")
save(icon(32), "docs/favicon-32.png")

let og = canvas(1200, 630) { c in
    c.setFillColor(green); c.fill(CGRect(x: 0, y: 0, width: 1200, height: 630))
    c.setFillColor(gold); c.fill(CGRect(x: 72, y: 470, width: 90, height: 12))
    text(c, "WISCONSIN", font: heavy(128), color: white, at: CGPoint(x: 66, y: 322))
    text(c, "EATS", font: heavy(128), color: gold, at: CGPoint(x: 66, y: 204))
    text(c, "Fish fry & supper club guide · every restaurant in the state", font: NSFont.systemFont(ofSize: 32, weight: .semibold), color: white, at: CGPoint(x: 70, y: 150))
    text(c, "Free for iPhone and iPad", font: NSFont.systemFont(ofSize: 30, weight: .regular), color: gold, at: CGPoint(x: 70, y: 96))
    cheese(c, x: 880, y: 330, w: 250, hole: green)
}
save(og, "docs/og.png")
