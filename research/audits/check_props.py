import json

print("=" * 60)
print("PLAYER PROPS (DET & BUF)")
print("=" * 60)
props = json.load(open('data/player_props_live.json'))['players']
target_names = [
    'Josh Allen', 'Jahmyr Gibbs', 'Amon-Ra St. Brown', 'Jared Goff', 
    'James Cook', 'James Cook III', 'Jameson Williams', 'DJ Moore', 
    'Khalil Shakir', 'Dalton Kincaid', 'Sam LaPorta', 'Keon Coleman', 
    'Tyler Bass', 'Jake Bates', 'Joshua Palmer', 'Ray Davis', 'Sione Vaki'
]

for name in target_names:
    found = None
    for p in props:
        if name.lower() == p.lower():
            found = p
            break
    if found:
        print(f"\n*** {found} ***")
        for cat, val in props[found].items():
            line = val.get('consensus_line')
            print(f"  {cat}: consensus={line}")
            # check any TD odds
            if 'Touchdowns' in cat:
                books = val.get('books', {})
                for b, bdata in list(books.items())[:3]:
                    print(f"    {b}: {bdata}")
    else:
        print(f"{name}: not found")
