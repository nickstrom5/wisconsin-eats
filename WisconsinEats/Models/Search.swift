import Foundation

/// Search that matches the start of words, the way the web leaderboard does:
/// "kopp" finds Kopp's, "north ave" finds N Ave, "st germain" = "saint germain", a town in the query narrows to that town,
/// and "fish fry", "supper club" or "custard" mean those Wisconsin classics (or a place named that way).
struct Search {
    static let typeSynonyms = ["avenue": "ave", "av": "ave", "street": "st", "boulevard": "blvd", "road": "rd", "drive": "dr", "place": "pl",
                               "court": "ct", "parkway": "pkwy", "highway": "hwy", "lane": "ln", "trail": "trl", "circle": "cir", "terrace": "ter"]
    static let synonyms: [String: String] = typeSynonyms.merging(["north": "n", "south": "s", "east": "e", "west": "w", "saint": "st", "mount": "mt", "fort": "ft"]) { a, _ in a }
    static let abbreviations = Set(synonyms.values)
    static let typeAbbreviations = Set(typeSynonyms.values)
    static let tagPhrases: [(String, PlaceTags)] = [("friday fish fry", .fishFry), ("fish fries", .fishFry), ("fish fry", .fishFry), ("fishfry", .fishFry),
                                                   ("supper clubs", .supperClub), ("supper club", .supperClub), ("supperclub", .supperClub),
                                                   ("frozen custard", .custard), ("custard", .custard), ("fish boil", .fishBoil),
                                                   ("cheese curds", .cheeseCurds), ("curds", .cheeseCurds)]

    /// Lowercase, no accents or apostrophes, "&" as "and" ("B&B" stays "bb"), everything else a single space.
    static func normalize(_ s: String) -> String {
        var t = s.folding(options: [.diacriticInsensitive, .caseInsensitive], locale: .init(identifier: "en_US")).lowercased()
        t = t.replacingOccurrences(of: #"\b([a-z0-9])\s*&\s*([a-z0-9])\b"#, with: "$1$2", options: .regularExpression)
        t = t.replacingOccurrences(of: "&", with: " and ")
        t = t.replacingOccurrences(of: #"['’`]"#, with: "", options: .regularExpression)
        t = t.replacingOccurrences(of: #"[^\p{L}\p{N}]+"#, with: " ", options: .regularExpression)
        return t.trimmingCharacters(in: .whitespaces)
    }

    /// Addresses (only) get their street words abbreviated so "north avenue" finds "N Ave".
    static func normalizeAddress(_ s: String) -> String {
        normalize(s).split(separator: " ").map { synonyms[String($0)] ?? String($0) }.joined(separator: " ")
    }

    struct Query {
        var tokens: [[String]] = []     // each token: needles, any of which may match
        var town: String?
        var townPhrase: String?
        var tag: PlaceTags?
        var tagPhrase: String?
        var isEmpty: Bool { tokens.isEmpty && town == nil && tag == nil }
    }

    /// `towns` maps a normalized town name ("st germain", "fond du lac") to its display name.
    static func parse(_ text: String, towns: [String: String]) -> Query {
        var q = Query()
        var raw = normalize(text).split(separator: " ").map(String.init)
        guard !raw.isEmpty else { return q }
        var mapped = raw.map { synonyms[$0] ?? $0 }
        func find(_ phrase: String) -> Range<Int>? {
            let p = phrase.split(separator: " ").map(String.init)
            guard p.count <= mapped.count else { return nil }
            for i in 0...(mapped.count - p.count) where Array(mapped[i..<i + p.count]) == p { return i..<i + p.count }
            return nil
        }
        func cut(_ r: Range<Int>) -> String {
            let words = raw[r].joined(separator: " ")
            raw.removeSubrange(r); mapped.removeSubrange(r)
            return words
        }
        for (phrase, tag) in tagPhrases {
            if let r = find(normalize(phrase)) { q.tag = tag; q.tagPhrase = cut(r); break }
        }
        // the longest town named in the query wins, unless a street type follows it ("green bay rd" is a street)
        for key in towns.keys.sorted(by: { $0.count > $1.count }) {
            if let r = find(key), !(r.upperBound < mapped.count && typeAbbreviations.contains(mapped[r.upperBound])) {
                q.town = towns[key]; q.townPhrase = cut(r); break
            }
        }
        let stop: Set<String> = ["the", "and", "of", "a", "in", "near"]
        var idx = Array(raw.indices)
        if idx.contains(where: { !stop.contains(mapped[$0]) }) { idx = idx.filter { !stop.contains(mapped[$0]) } }
        for (n, i) in idx.enumerated() {
            let token = raw[i], isLast = n == idx.count - 1
            if let abbr = synonyms[token] { q.tokens.append([" \(abbr) ", " \(token)"]); continue }
            let whole = (abbreviations.contains(token) && (!isLast || token.count > 1)) || (token.count <= 2 && !isLast)
            var needles = [" " + token + (whole ? " " : "")]
            if isLast && token.count >= 3 {
                for (word, abbr) in typeSynonyms where word != token && word.hasPrefix(token) { needles.append(" \(abbr) ") }
            }
            q.tokens.append(needles)
        }
        // "brady st": a finished street type sticks to the word before it
        if q.tokens.count >= 2, let last = idx.last, typeAbbreviations.contains(mapped[last]) {
            let prev = idx[idx.count - 2]
            q.tokens.removeLast(2)
            q.tokens.append([" \(mapped[prev]) \(mapped[last]) ", " \(raw[prev]) \(raw[last])"])
        }
        return q
    }

    static func matches(_ p: Place, _ q: Query) -> Bool {
        if let tag = q.tag, !p.tags.contains(tag) {
            let stem = normalize(q.tagPhrase ?? "").replacingOccurrences(of: #"s$"#, with: "", options: .regularExpression)
            if stem.isEmpty || !p.nameText.contains(" " + stem) { return false }
        }
        if let town = q.town, p.city != town {
            if !p.nameText.contains(" " + normalize(q.townPhrase ?? "")) { return false }
        }
        for needles in q.tokens where !needles.contains(where: { p.searchText.contains($0) }) { return false }
        return true
    }

    /// Name matches first ("grand" puts Grand Avenue Cafe ahead of places in Grand Chute).
    static func nameMatches(_ p: Place, _ q: Query) -> Bool {
        !q.tokens.isEmpty && q.tokens.allSatisfy { needles in needles.contains { p.nameText.contains($0) } }
    }
}
