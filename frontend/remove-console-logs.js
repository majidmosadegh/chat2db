const fs = require('fs');
const path = require('path');

// Function to remove console.log statements from a file
function removeConsoleLogs(filePath) {
  try {
    let content = fs.readFileSync(filePath, 'utf8');
    const originalContent = content;
    
    // Remove console.log, console.info, console.debug (but keep console.error and console.warn for now)
    // Pattern: console.log(...) or console.log(...);
    content = content.replace(/console\.(log|info|debug)\([^)]*\);?\s*/g, '');
    content = content.replace(/console\.(log|info|debug)\([^)]*\)\s*/g, '');
    
    // Remove console.error that are just for debugging (not critical errors)
    // Keep errors that are in catch blocks or error handlers
    content = content.replace(/console\.error\([^)]*\);?\s*(?=\/\/)/g, '');
    
    // Remove standalone console.error in non-critical contexts
    // This is a bit aggressive but necessary for production
    const lines = content.split('\n');
    const filteredLines = lines.filter((line, index) => {
      // Keep console.error in error boundaries and critical error handlers
      if (line.includes('console.error') && (
        line.includes('ErrorBoundary') ||
        line.includes('error boundary') ||
        line.includes('catch (error)') ||
        lines[index - 1]?.includes('catch (error)') ||
        lines[index - 1]?.includes('catch(')
      )) {
        return true; // Keep critical error logs
      }
      // Remove debug console.error
      if (line.includes('console.error') && !line.includes('ErrorBoundary')) {
        return false;
      }
      return true;
    });
    
    content = filteredLines.join('\n');
    
    // Only write if content changed
    if (content !== originalContent) {
      fs.writeFileSync(filePath, content, 'utf8');
      return true;
    }
    return false;
  } catch (error) {
    console.error(`Error processing ${filePath}:`, error.message);
    return false;
  }
}

// Recursively find all .tsx and .ts files
function findFiles(dir, fileList = []) {
  const files = fs.readdirSync(dir);
  
  files.forEach(file => {
    const filePath = path.join(dir, file);
    const stat = fs.statSync(filePath);
    
    if (stat.isDirectory()) {
      // Skip node_modules, .next, and other build directories
      if (!file.startsWith('.') && file !== 'node_modules' && file !== '.next' && file !== 'venv') {
        findFiles(filePath, fileList);
      }
    } else if (file.endsWith('.tsx') || file.endsWith('.ts')) {
      fileList.push(filePath);
    }
  });
  
  return fileList;
}

// Main execution
const frontendDir = __dirname;
const files = findFiles(frontendDir);

console.log(`Found ${files.length} files to process`);

let processed = 0;
files.forEach(file => {
  if (removeConsoleLogs(file)) {
    processed++;
    console.log(`Processed: ${file}`);
  }
});

console.log(`\nProcessed ${processed} files`);

