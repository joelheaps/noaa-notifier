coords: tuple[list[float], ...] = (
    [-104.05283, 41.697954],
    [-104.053249, 41.001406],
    [-102.051614, 41.002377],
    [-102.051744, 40.003078],
    [-98.934792, 40.002205],
    [-95.30829, 39.999998],
    [-95.883178, 40.717579],
    [-96.064537, 41.793002],
    [-96.724033, 42.665971],
    [-97.257089, 42.853854],
    [-97.950147, 42.769619],
    [-98.49855, 42.99856],
    [-101.625424, 42.996238],
    [-104.053127, 43.000585],
    [-104.05283, 41.697954],
)

x_min = min(coord[0] for coord in coords)
x_max = max(coord[0] for coord in coords)
y_min = min(coord[1] for coord in coords)
y_max = max(coord[1] for coord in coords)

# Print in form {xmin: -104, ymin: 35.6, xmax: -94.32, ymax: 41}
print(f"{{xmin: {x_min}, ymin: {y_min}, xmax: {x_max}, ymax: {y_max}}}")
