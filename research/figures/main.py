import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, ArrowStyle

def add_arrow(ax, start, end, text, color='black'):
    arrow_style = ArrowStyle("-|>", head_length=2, head_width=2)
    ax.annotate('', xy=end, xytext=start,
                arrowprops=dict(arrowstyle=arrow_style, color=color, lw=2))
    mid_point = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
    ax.annotate(text, xy=mid_point, textcoords="offset points", xytext=(0, 10),
                ha='center', va='center', fontsize=12, color=color)

fig, ax = plt.subplots(figsize=(12, 8))

# Add the main steps in the process
steps = ["Data Collection", "Upload to Platform", "Labeling by Crowd Workers", "Quality Control", "Final Dataset Compilation"]
positions = [(1, 4), (3, 4), (5, 4), (7, 4), (9, 4)]

# Add sub-steps for each main step
sub_steps = {
    "Data Collection": ["Camera Traps", "Field Surveys", "Citizen Science"],
    "Upload to Platform": ["Data Formatting", "Metadata Addition"],
    "Labeling by Crowd Workers": ["Species Identification", "Behavior Annotation"],
    "Quality Control": ["Expert Review", "Consensus Check"],
    "Final Dataset Compilation": ["Data Integration", "Preparation for Analysis"]
}

# Add steps to the plot
for pos, step in zip(positions, steps):
    ax.text(pos[0], pos[1], step, ha='center', va='center', fontsize=14, bbox=dict(facecolor='lightblue', edgecolor='black', boxstyle="round,pad=0.5"))

    sub_pos_y = pos[1] - 1
    for sub_step in sub_steps[step]:
        ax.text(pos[0], sub_pos_y, sub_step, ha='center', va='center', fontsize=10, bbox=dict(facecolor='lightgreen', edgecolor='black', boxstyle="round,pad=0.3"))
        sub_pos_y -= 0.5

# Add arrows between steps
arrow_positions = [((2, 3.5), (3, 3.5), "Upload"), 
                   ((4, 3.5), (5, 3.5), "Labeling"),
                   ((6, 3.5), (7, 3.5), "Review"),
                   ((8, 3.5), (9, 3.5), "Compile")]

for start, end, text in arrow_positions:
    add_arrow(ax, start, end, text)

# Set plot limits and remove axes
ax.set_xlim(0, 10)
ax.set_ylim(0, 5)
ax.axis('off')

# Add a title
plt.title("Crowdsourcing Data Labeling Process for Tsushima Yamaneko Project", fontsize=16)

plt.tight_layout()
plt.show()
