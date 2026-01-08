# cgal-rosetta

Python bindings for cgal using rosetta

## Prerequisites

- CMake 3.16+
- C++20 compatible compiler
- Python 3.8+ (for Python bindings)

## Building

```bash
# Create build directory
mkdir build && cd build

# Configure
cmake ..

# Build the generator
make

# Run the generator
cd ..
./cgal_rosetta_generator project.json
```

## Generated Bindings

This project generates bindings for: python

After running the generator, you'll find the generated code in the `generated/` directory.

### Python Bindings

```bash
cd generated/python
pip install .
```

Then in Python:

```python
import cgal
# Use your bound classes and functions
```

## Customizing Bindings

Edit `bindings/cgal_rosetta_registration.h` to register your C++ classes and functions.

See the [Rosetta documentation](https://github.com/xaliphostes/rosetta) for more information on registration macros.

## License

MIT
