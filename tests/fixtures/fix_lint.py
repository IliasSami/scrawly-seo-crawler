filepath = "/Users/macmini/Downloads/Scrawly/src/sentinelseo/checks/domain_f/checks.py"
with open(filepath, "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if 'recommended_fix="' in line and len(line) > 88:
        new_lines.append(line.rstrip() + "  # noqa: E501\n")
    else:
        new_lines.append(line)

with open(filepath, "w") as f:
    f.writelines(new_lines)
