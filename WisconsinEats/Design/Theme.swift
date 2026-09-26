import SwiftUI

/// Green-and-gold Wisconsin palette, light only. Gold is always a fill with green text on it (gold text on white fails contrast).
enum Theme {
    static let green = Color(hex: 0x203731)
    static let green2 = Color(hex: 0x2D5242)
    static let gold = Color(hex: 0xFFB612)
    static let goldSoft = Color(hex: 0xFFE7A8)
    static let ink = Color(hex: 0x14241D)
    static let ink2 = Color(hex: 0x2E4238)
    static let muted = Color(hex: 0x53665B)
    static let surface = Color.white
    static let surface2 = Color(hex: 0xF1F5F2)
    static let surface3 = Color(hex: 0xE1EAE4)
    static let rule = Color(hex: 0xDAE3DD)
    static let rule2 = Color(hex: 0xB6C6BC)

    /// Condensed, heavy display type for titles and big numbers (the system font's compressed width).
    static func display(_ size: CGFloat, weight: Font.Weight = .black) -> Font {
        .system(size: size, weight: weight).width(.compressed)
    }

    static let gradeColors: [String: Color] = [
        "A": Color(hex: 0x12733A), "B": Color(hex: 0x4B7A1B), "C": Color(hex: 0xF2B01E), "D": Color(hex: 0xE8804F), "F": Color(hex: 0xC1302F),
    ]
}

extension Color {
    init(hex: UInt32) {
        self.init(red: Double((hex >> 16) & 0xFF) / 255, green: Double((hex >> 8) & 0xFF) / 255, blue: Double(hex & 0xFF) / 255)
    }
}

/// A small uppercase label: "SUPPER CLUB", "LICENSED".
struct Chip: View {
    enum Style { case gold, green, plain, dashed }
    let text: String
    var style: Style = .plain

    var body: some View {
        Text(text.uppercased())
            .font(.system(size: 10.5, weight: .bold))
            .tracking(0.4)
            .padding(.horizontal, 7).padding(.vertical, 3)
            .foregroundStyle(style == .green ? Color.white : style == .dashed ? Theme.muted : Theme.green)
            .background {
                RoundedRectangle(cornerRadius: 5).fill(style == .gold ? Theme.goldSoft : style == .green ? Theme.green : style == .dashed ? .clear : Theme.surface2)
            }
            .overlay {
                if style == .dashed { RoundedRectangle(cornerRadius: 5).strokeBorder(Theme.rule2, style: StrokeStyle(lineWidth: 1, dash: [3, 2])) }
            }
            .accessibilityLabel(text)
    }
}

struct GradeBadge: View {
    let grade: String
    var size: CGFloat = 22

    var body: some View {
        Text(grade)
            .font(Theme.display(size * 0.72))
            .foregroundStyle(grade == "C" || grade == "D" ? Color(hex: 0x2B1D00) : .white)
            .frame(width: size, height: size)
            .background(RoundedRectangle(cornerRadius: size * 0.27).fill(Theme.gradeColors[grade] ?? Theme.muted))
            .accessibilityLabel("Inspection grade \(grade)")
    }
}
