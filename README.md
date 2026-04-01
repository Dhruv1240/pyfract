# Modularizer

A powerful Python CLI tool that uses AI to automatically refactor large Python files into smaller, cohesive modules. Perfect for breaking down monolithic scripts into maintainable, importable components.

## Features

- **AI-Powered Planning**: Uses the OpenAI Python SDK (`OpenAI(...).chat.completions.create`) against a compatible API (default base `https://ai.aimlapi.com`, model `gpt-5.2-2025-12-11`)
- **AI-first by default**: If the model fails after retries, the run stops with an error unless you pass `--heuristic-fallback` or use `--offline` for heuristic-only mode
- **Robust Dependency Detection**: AST-based analysis of function calls, class relationships, type annotations, and base classes
- **Smart Import Handling**: AST-based import extraction (not string-based) that handles all Python import formats 
- **Execution Validation**: Generated modules are validated to ensure they can be imported and executed
- **Strict AI Validation**: AI-generated plans are strictly validated to prevent duplicate segments and orphaned code
- **Cross-Module Imports**: Modules can import from other generated modules as needed
- **Deep Dependency Graph**: Connected-component analysis to group related code together
- **Configuration Files**: Save and reuse settings with JSON config files
- **Verbose Output**: Detailed progress reporting for debugging 

## Installation

### Requirements

- Python 3.8+
- `openai` for chat completions (OpenAI-compatible clients, e.g. AIMLAPI)
- `typer` for CLI interface
- `ast` (built-in) for code analysis

### Install Dependencies

```bash
pip install openai typer
```

## Quick Start

### Desktop UI (Easiest for end users)

You can run a desktop GUI instead of CLI:

```bash
python modulizer_gui.py
```

The UI lets users:
- choose input/output paths
- set model, API key, and base URL (defaults match AIMLAPI)
- enable or disable offline mode
- set planning controls (`max modules`, `min segments/module`, `AI retries`)
- tune semantic grouping with keywords
- run strict validation

### Build Windows Executable (.exe)

Use the included PowerShell script:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

After build, the executable is at:

```text
dist\ModulizerUI.exe
```

### Basic Usage

```bash
# Modularize a Python file using AI planning
python modulizer.py modularize --input-file my_large_script.py --output-dir ./modules

# Use offline heuristic planning (no API key needed)
python modulizer.py modularize --input-file my_large_script.py --output-dir ./modules --offline
```

### Generate Configuration

```bash
# Create a sample config file
python modulizer.py init-config

# Or specify a custom path
python modulizer.py init-config --output-file my_config.json
```

### Use Configuration

```bash
# Load settings from config file
python modulizer.py modularize --input-file script.py --output-dir modules --config config.json
```

## Command Reference

### `modularize`

Split a Python file into modules.

```bash
python modulizer.py modularize [OPTIONS]
```

**Required Options:**
- `--input-file PATH`: Python file to split (must have .py extension)
- `--output-dir PATH`: Directory to write generated modules

**Optional Options:**
- `--model TEXT`: Chat model (default: `gpt-5.2-2025-12-11`)
- `--api-key TEXT`: API key (or set `OPENAI_API_KEY`)
- `--openai-base-url TEXT`: API base URL (overrides `OPENAI_BASE_URL`; default `https://ai.aimlapi.com`)
- `--temperature`, `--top-p`, `--top-k`, `--frequency-penalty`: sampling (defaults `0.9`, `0.3`, `20`, `0.8`)
- `--offline`: Heuristic planning only (no AI)
- `--heuristic-fallback`: If AI fails after retries, fall back to heuristic planning (off by default)
- `--config PATH`: JSON config file to load settings from
- `--verbose`: Enable detailed progress output

### `version`

Show version information.

```bash
python modulizer.py version
```

### `init-config`

Generate a sample configuration file.

```bash
python modulizer.py init-config [OPTIONS]
```

**Options:**
- `--output-file PATH`: Path for the config file (default: modulizer_config.json)

## Configuration File

Configuration files allow you to save common settings. Here's an example:

```json
{
  "model": "gpt-5.2-2025-12-11",
  "api_key": "<YOUR_API_KEY>",
  "openai_base_url": "https://ai.aimlapi.com",
  "temperature": 0.9,
  "top_p": 0.3,
  "top_k": 20,
  "frequency_penalty": 0.8,
  "verbose": false
}
```

Command-line options always override config file settings.

## Examples

### Example 1: Basic AI-Powered Modularization

```bash
# Set your API key
export OPENAI_API_KEY="your_key_here"

# Modularize with AI assistance
python modulizer.py modularize \
  --input-file large_app.py \
  --output-dir app_modules \
  --verbose
```

### Example 2: Offline Mode with Custom Model

```bash
python modulizer.py modularize \
  --input-file script.py \
  --output-dir modules \
  --offline \
  --model "custom-model"
```

### Example 3: Using Configuration Files

```bash
# Create config
python modulizer.py init-config --output-file my_settings.json

# Edit my_settings.json to add your API key and preferences

# Use the config
python modulizer.py modularize \
  --input-file app.py \
  --output-dir modules \
  --config my_settings.json
```

## Output Structure

After running modularization, you'll get:

```
output_dir/
├── module_plan.json      # Manifest with refactoring details
├── __init__.py          # Package initialization
├── utils_module_1.py    # Generated module 1
├── handlers_module_2.py # Generated module 2
└── ...
```

### Module Plan JSON

The `module_plan.json` contains:
- Original file information
- List of generated modules with descriptions
- Segment mappings
- Shared helpers notes

## How It Works

1. **Analysis**: 
   - Parses the Python AST to identify top-level segments (functions, classes, etc.)
   - Extracts dependencies by analyzing function calls and class relationships
   - Detects which functions and classes interact with each other

2. **Intelligent Planning**: 
   - **With AI**: Sends code segments and dependencies to LLM for intelligent grouping
   - **Without AI** (offline mode): Uses relationship analysis to create functional modules:
     * Builds a dependency graph between code segments
     * Groups functions that call each other
     * Places classes with their helper functions
     * Creates connected components of related code

3. **Smart Module Generation**: 
   - Extracts all necessary imports from the original file
   - Determines which imports each module needs
   - Includes only required imports to avoid unnecessary dependencies
   - Ensures each module is self-contained and runnable
   - Preserves code functionality and relationships

## Troubleshooting

### Common Issues

**"Missing OpenAI API key"**
```bash
# Set environment variable
export OPENAI_API_KEY="your_key_here"

# Or use --api-key option
python modulizer.py modularize --api-key "your_key" ...
```

**"Input file must be a Python file"**
- Ensure your input file has a `.py` extension
- Check that the file exists and is readable

**"Invalid Python syntax"**
- The input file must be valid Python code
- Fix any syntax errors before modularizing

**AI Planning Fails**
- By default the run **exits** so you can fix API/model issues or increase `--ai-retries` (default 5)
- Add `--heuristic-fallback` if you explicitly want heuristic planning after AI failure
- Use `--offline` only when you want heuristic-only mode (no API)

### Verbose Mode

Use `--verbose` to see detailed progress:

```bash
python modulizer.py modularize --input-file file.py --output-dir modules --verbose
```

This shows:
- Source file analysis progress
- Number of segments detected
- Planning phase details
- Module writing progress

## Advanced Usage

### Custom AI Models

```bash
# Official OpenAI instead of AIMLAPI default
python modulizer.py modularize \
  --input-file script.py \
  --output-dir modules \
  --openai-base-url "https://api.openai.com/v1" \
  --model "gpt-4o"
```

### Batch Processing

For multiple files, you can create a simple script:

```bash
#!/bin/bash
for file in *.py; do
  python modulizer.py modularize \
    --input-file "$file" \
    --output-dir "modules/$(basename "$file" .py)" \
    --offline
done
```

## Why Intelligent Heuristics Are Important

You raised a valid concern: heuristic-only planning can break code by splitting dependent functions and classes. The modularizer now addresses this with:

- **Dependency Tracking**: Analyzes actual function calls and class relationships
- **Connected Components**: Groups code that depends on each other in the same module
- **Smart Fallback**: Only uses heuristics when AI fails, with built-in relationship analysis
- **Import Management**: Automatically includes all necessary imports so modules remain functional
- **Functional Testing**: Generated modules are tested to ensure they import correctly

Without these improvements, you'd get modules like:
```
❌ BAD: DataManager class in one module, load_data and save_data functions in another (broken)
```

With the smart heuristic, you get:
```
✅ GOOD: DataManager, load_data, and save_data grouped together with proper imports (functional)
```

## License

This project is open source. See LICENSE file for details.

## Support

For issues and questions:
- Check the troubleshooting section above
- Use `--verbose` mode for detailed error information
- Ensure your Python file is syntactically valid before processing

