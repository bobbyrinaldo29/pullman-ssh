import * as monaco from 'monaco-editor'
import Parser from 'web-tree-sitter'

import treeSitterWasmUrl from 'web-tree-sitter/tree-sitter.wasm?url'
import phpWasmUrl from 'tree-sitter-wasms/out/tree-sitter-php.wasm?url'
import jsWasmUrl from 'tree-sitter-wasms/out/tree-sitter-javascript.wasm?url'
import tsWasmUrl from 'tree-sitter-wasms/out/tree-sitter-typescript.wasm?url'
import htmlWasmUrl from 'tree-sitter-wasms/out/tree-sitter-html.wasm?url'
import cssWasmUrl from 'tree-sitter-wasms/out/tree-sitter-css.wasm?url'
import jsonWasmUrl from 'tree-sitter-wasms/out/tree-sitter-json.wasm?url'
import pythonWasmUrl from 'tree-sitter-wasms/out/tree-sitter-python.wasm?url'
import bashWasmUrl from 'tree-sitter-wasms/out/tree-sitter-bash.wasm?url'

let isInitialized = false
let initPromise: Promise<void> | null = null

const languageWasmMap: Record<string, string> = {
  php: phpWasmUrl,
  javascript: jsWasmUrl,
  typescript: tsWasmUrl,
  html: htmlWasmUrl,
  css: cssWasmUrl,
  json: jsonWasmUrl,
  python: pythonWasmUrl,
  shell: bashWasmUrl,
  bash: bashWasmUrl
}

const loadedLanguages = new Map<string, any>()
const modelTreeMap = new Map<string, { tree: Parser.Tree; version: number }>()

export interface BreadcrumbSymbol {
  name: string
  kind: string
  range: {
    startLineNumber: number
    startColumn: number
    endLineNumber: number
    endColumn: number
  }
}

/**
 * Initializes the Tree-sitter WASM engine and registers Monaco Folding & Symbol Providers.
 */
export async function initTreeSitterService(monacoInstance: typeof monaco): Promise<void> {
  if (isInitialized) return
  if (initPromise) return initPromise

  initPromise = (async () => {
    try {
      await Parser.init({
        locateFile() {
          return treeSitterWasmUrl
        }
      })
      isInitialized = true

      // Register AST-based Folding and Symbol providers for supported languages
      const languages = Object.keys(languageWasmMap)
      for (const lang of languages) {
        registerProvidersForLanguage(monacoInstance, lang)
      }
    } catch (err) {
      console.warn('Failed to initialize Web Tree-sitter:', err)
    }
  })()

  return initPromise
}

async function getOrLoadLanguage(langId: string): Promise<any | null> {
  if (!isInitialized) return null
  const wasmUrl = languageWasmMap[langId]
  if (!wasmUrl) return null

  if (loadedLanguages.has(langId)) {
    return loadedLanguages.get(langId)
  }

  try {
    const lang = await Parser.Language.load(wasmUrl)
    loadedLanguages.set(langId, lang)
    return lang
  } catch (err) {
    console.warn(`Failed to load Tree-sitter grammar for ${langId}:`, err)
    return null
  }
}

export async function parseModelAST(
  model: monaco.editor.ITextModel,
  langId: string
): Promise<Parser.Tree | null> {
  const lang = await getOrLoadLanguage(langId)
  if (!lang) return null

  const uri = model.uri.toString()
  const cached = modelTreeMap.get(uri)
  if (cached && cached.version === model.getVersionId()) {
    return cached.tree
  }

  const parser = new Parser()
  parser.setLanguage(lang)
  const code = model.getValue()
  const tree = parser.parse(code)
  modelTreeMap.set(uri, { tree, version: model.getVersionId() })
  return tree
}

function registerProvidersForLanguage(monacoInstance: typeof monaco, langId: string): void {
  // 1. Accurate Tree-sitter AST Folding Provider
  monacoInstance.languages.registerFoldingRangeProvider(langId, {
    async provideFoldingRanges(model) {
      const tree = await parseModelAST(model, langId)
      if (!tree) return []

      const ranges: monaco.languages.FoldingRange[] = []
      const foldingTypes = new Set([
        'compound_statement',
        'declaration_list',
        'switch_block',
        'case_statement',
        'statement_block',
        'class_declaration',
        'method_declaration',
        'function_declaration',
        'function_definition',
        'object',
        'array',
        'array_creation_expression',
        'arguments',
        'formal_parameters',
        'comment',
        'element',
        'rule_set',
        'block'
      ])

      function traverse(node: Parser.SyntaxNode) {
        if (
          foldingTypes.has(node.type) &&
          node.startPosition.row < node.endPosition.row
        ) {
          ranges.push({
            start: node.startPosition.row + 1,
            end: node.endPosition.row + 1,
            kind: node.type.includes('comment')
              ? monacoInstance.languages.FoldingRangeKind.Comment
              : monacoInstance.languages.FoldingRangeKind.Region
          })
        }

        for (let i = 0; i < node.childCount; i++) {
          const child = node.child(i)
          if (child) traverse(child)
        }
      }

      traverse(tree.rootNode)
      return ranges
    }
  })

  // 2. Hierarchical Document Symbol Provider (AST Outline & Cmd+Shift+O)
  monacoInstance.languages.registerDocumentSymbolProvider(langId, {
    async provideDocumentSymbols(model) {
      const tree = await parseModelAST(model, langId)
      if (!tree) return []

      const symbols: monaco.languages.DocumentSymbol[] = []

      function extractSymbols(node: Parser.SyntaxNode): monaco.languages.DocumentSymbol[] {
        const result: monaco.languages.DocumentSymbol[] = []

        const isFunction =
          node.type === 'function_declaration' ||
          node.type === 'function_definition' ||
          node.type === 'arrow_function'
        const isMethod = node.type === 'method_declaration'
        const isClass = node.type === 'class_declaration' || node.type === 'interface_declaration'
        const isProperty = node.type === 'property_element' || node.type === 'field_declaration'

        if (isFunction || isMethod || isClass || isProperty) {
          const nameNode =
            node.childForFieldName('name') ||
            node.children.find(
              (c) =>
                c.type === 'name' ||
                c.type === 'identifier' ||
                c.type === 'property_identifier' ||
                c.type === 'variable_name'
            )

          const name = nameNode ? nameNode.text : `<anonymous>`
          let kind = monaco.languages.SymbolKind.Function
          if (isClass) kind = monaco.languages.SymbolKind.Class
          else if (isMethod) kind = monaco.languages.SymbolKind.Method
          else if (isProperty) kind = monaco.languages.SymbolKind.Property

          const symbolRange: monaco.IRange = {
            startLineNumber: node.startPosition.row + 1,
            startColumn: node.startPosition.column + 1,
            endLineNumber: node.endPosition.row + 1,
            endColumn: node.endPosition.column + 1
          }

          const selectionRange: monaco.IRange = nameNode
            ? {
                startLineNumber: nameNode.startPosition.row + 1,
                startColumn: nameNode.startPosition.column + 1,
                endLineNumber: nameNode.endPosition.row + 1,
                endColumn: nameNode.endPosition.column + 1
              }
            : symbolRange

          const children: monaco.languages.DocumentSymbol[] = []
          for (let i = 0; i < node.childCount; i++) {
            const child = node.child(i)
            if (child) children.push(...extractSymbols(child))
          }

          result.push({
            name,
            detail: node.type.replace(/_/g, ' '),
            kind,
            tags: [],
            range: symbolRange,
            selectionRange,
            children
          })
        } else {
          for (let i = 0; i < node.childCount; i++) {
            const child = node.child(i)
            if (child) result.push(...extractSymbols(child))
          }
        }

        return result
      }

      symbols.push(...extractSymbols(tree.rootNode))
      return symbols
    }
  })
}

/**
 * Resolves the hierarchical breadcrumb symbols for the given cursor position using Tree-sitter AST.
 */
export async function getEnclosingSymbolsAtPosition(
  model: monaco.editor.ITextModel,
  langId: string,
  lineNumber: number,
  column: number
): Promise<BreadcrumbSymbol[]> {
  const tree = await parseModelAST(model, langId)
  if (tree) {
    const point: Parser.Point = {
      row: Math.max(0, lineNumber - 1),
      column: Math.max(0, column - 1)
    }

    const results: BreadcrumbSymbol[] = []
    let currentNode: Parser.SyntaxNode | null = tree.rootNode.descendantForPosition(point)

    while (currentNode) {
      const isNamedSymbol =
        currentNode.type === 'class_declaration' ||
        currentNode.type === 'interface_declaration' ||
        currentNode.type === 'method_declaration' ||
        currentNode.type === 'function_declaration' ||
        currentNode.type === 'function_definition'

      if (isNamedSymbol) {
        const nameNode =
          currentNode.childForFieldName('name') ||
          currentNode.children.find(
            (c) =>
              c.type === 'name' ||
              c.type === 'identifier' ||
              c.type === 'property_identifier' ||
              c.type === 'variable_name'
          )

        if (nameNode) {
          results.unshift({
            name: nameNode.text,
            kind: currentNode.type.includes('class')
              ? 'Class'
              : currentNode.type.includes('method')
                ? 'Method'
                : 'Function',
            range: {
              startLineNumber: currentNode.startPosition.row + 1,
              startColumn: currentNode.startPosition.column + 1,
              endLineNumber: currentNode.endPosition.row + 1,
              endColumn: currentNode.endPosition.column + 1
            }
          })
        }
      }

      currentNode = currentNode.parent
    }

    if (results.length > 0) return results
  }

  // Fallback to regex-based outline symbols
  const outline = await getDocumentOutlineSymbols(model, langId)
  const fallbackResults: BreadcrumbSymbol[] = []

  function findEnclosing(list: DocumentOutlineSymbol[]) {
    for (const item of list) {
      if (
        item.range.startLineNumber <= lineNumber &&
        item.range.endLineNumber >= lineNumber
      ) {
        fallbackResults.push({
          name: item.name,
          kind: item.kind,
          range: item.range
        })
        if (item.children) findEnclosing(item.children)
      }
    }
  }

  findEnclosing(outline)
  return fallbackResults
}

export interface DocumentOutlineSymbol {
  id: string
  name: string
  kind: 'Class' | 'Method' | 'Function' | 'Variable' | 'Property' | 'Interface'
  range: {
    startLineNumber: number
    startColumn: number
    endLineNumber: number
    endColumn: number
  }
  children?: DocumentOutlineSymbol[]
}

/**
 * Extracts full hierarchical outline symbols (Classes, Methods, Functions, Variables) for the breadcrumb symbol picker.
 */
export async function getDocumentOutlineSymbols(
  model: monaco.editor.ITextModel,
  langId: string
): Promise<DocumentOutlineSymbol[]> {
  try {
    const tree = await parseModelAST(model, langId)
    if (tree) {
      let symIdCounter = 0

      function extractOutline(node: Parser.SyntaxNode): DocumentOutlineSymbol[] {
        const list: DocumentOutlineSymbol[] = []

        for (let i = 0; i < node.childCount; i++) {
          const child = node.child(i)
          if (!child) continue

          // 1. Classes, Interfaces, Traits
          const isClass =
            child.type === 'class_declaration' ||
            child.type === 'class_definition' ||
            child.type === 'interface_declaration' ||
            child.type === 'trait_declaration'

          // 2. Methods & Functions
          const isMethod = child.type === 'method_declaration' || child.type === 'method_definition'
          const isFunction =
            child.type === 'function_declaration' ||
            child.type === 'function_definition' ||
            child.type === 'arrow_function'

          // 3. Properties & Fields
          const isProperty =
            child.type === 'property_declaration' ||
            child.type === 'property_element' ||
            child.type === 'field_declaration'

          // 4. Variables / Assignments
          const isPhpExpr = child.type === 'expression_statement'
          const isVarDecl =
            child.type === 'variable_declaration' ||
            child.type === 'lexical_declaration'

          if (isClass) {
            const nameNode =
              child.childForFieldName('name') ||
              child.children.find((c) => c.type === 'name' || c.type === 'identifier')
            const name = nameNode ? nameNode.text : 'Class'
            const bodyNode =
              child.childForFieldName('body') ||
              child.children.find(
                (c) =>
                  c.type === 'declaration_list' ||
                  c.type === 'class_body' ||
                  c.type === 'block'
              )

            const children = bodyNode ? extractOutline(bodyNode) : []
            list.push({
              id: `sym_${++symIdCounter}`,
              name,
              kind: child.type.includes('interface') ? 'Interface' : 'Class',
              range: {
                startLineNumber: child.startPosition.row + 1,
                startColumn: child.startPosition.column + 1,
                endLineNumber: child.endPosition.row + 1,
                endColumn: child.endPosition.column + 1
              },
              children
            })
          } else if (isMethod || isFunction) {
            const nameNode =
              child.childForFieldName('name') ||
              child.children.find((c) => c.type === 'name' || c.type === 'identifier')
            const name = nameNode ? nameNode.text : isMethod ? 'method' : 'function'
            list.push({
              id: `sym_${++symIdCounter}`,
              name,
              kind: isMethod ? 'Method' : 'Function',
              range: {
                startLineNumber: child.startPosition.row + 1,
                startColumn: child.startPosition.column + 1,
                endLineNumber: child.endPosition.row + 1,
                endColumn: child.endPosition.column + 1
              }
            })
          } else if (isProperty) {
            const nameNode =
              child.childForFieldName('name') ||
              child.children.find(
                (c) =>
                  c.type === 'name' ||
                  c.type === 'identifier' ||
                  c.type === 'variable_name'
              )
            if (nameNode) {
              list.push({
                id: `sym_${++symIdCounter}`,
                name: nameNode.text,
                kind: 'Property',
                range: {
                  startLineNumber: child.startPosition.row + 1,
                  startColumn: child.startPosition.column + 1,
                  endLineNumber: child.endPosition.row + 1,
                  endColumn: child.endPosition.column + 1
                }
              })
            }
          } else if (isPhpExpr) {
            const assign = child.children.find((c) => c.type === 'assignment_expression')
            if (assign) {
              const varNode = assign.childForFieldName('left') || assign.children[0]
              if (varNode && (varNode.text.startsWith('$') || varNode.type === 'variable_name')) {
                list.push({
                  id: `sym_${++symIdCounter}`,
                  name: varNode.text,
                  kind: 'Variable',
                  range: {
                    startLineNumber: child.startPosition.row + 1,
                    startColumn: child.startPosition.column + 1,
                    endLineNumber: child.endPosition.row + 1,
                    endColumn: child.endPosition.column + 1
                  }
                })
              }
            }
          } else if (isVarDecl) {
            for (let j = 0; j < child.childCount; j++) {
              const declarator = child.child(j)
              if (
                declarator &&
                (declarator.type === 'variable_declarator' ||
                  declarator.type === 'lexical_declaration')
              ) {
                const nameNode = declarator.childForFieldName('name') || declarator.children[0]
                if (nameNode) {
                  list.push({
                    id: `sym_${++symIdCounter}`,
                    name: nameNode.text,
                    kind: 'Variable',
                    range: {
                      startLineNumber: declarator.startPosition.row + 1,
                      startColumn: declarator.startPosition.column + 1,
                      endLineNumber: declarator.endPosition.row + 1,
                      endColumn: declarator.endPosition.column + 1
                    }
                  })
                }
              }
            }
          }
        }

        return list
      }

      const res = extractOutline(tree.rootNode)
      if (res.length > 0) return res
    }
  } catch (err) {
    console.warn('[Tree-sitter] Fallback to regex outline extractor:', err)
  }

  // Robust regex fallback
  return extractSymbolsRegex(model.getValue(), langId)
}

/**
 * Universal fast regex parser for extracting functions, classes, and top-level variables.
 */
export function extractSymbolsRegex(content: string, langId: string): DocumentOutlineSymbol[] {
  const lines = content.split('\n')
  const symbols: DocumentOutlineSymbol[] = []
  let currentClass: DocumentOutlineSymbol | null = null
  let braceDepth = 0
  let classBraceDepth = 0
  let symIdCounter = 0
  const isPhp = langId === 'php' || langId.includes('php')
  const isPy = langId === 'python' || langId === 'py'

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const trimmed = line.trim()
    const lineNum = i + 1

    if (
      !trimmed ||
      trimmed.startsWith('//') ||
      trimmed.startsWith('#') ||
      trimmed.startsWith('/*') ||
      trimmed.startsWith('*')
    ) {
      continue
    }

    // 1. PHP Variables
    if (isPhp && !currentClass) {
      const varMatch = line.match(/^\s*(\$[a-zA-Z_\x7f-\xff][a-zA-Z0-9_\x7f-\xff]*)\s*=/i)
      if (varMatch) {
        symbols.push({
          id: `var_${++symIdCounter}`,
          name: varMatch[1],
          kind: 'Variable',
          range: {
            startLineNumber: lineNum,
            startColumn: 1,
            endLineNumber: lineNum,
            endColumn: line.length
          }
        })
      }
    }

    // 2. Class / Interface / Trait
    const classMatch = line.match(/(?:class|interface|trait)\s+([a-zA-Z0-9_]+)/i)
    if (classMatch) {
      currentClass = {
        id: `cls_${++symIdCounter}`,
        name: classMatch[1],
        kind: classMatch[0].toLowerCase().includes('interface') ? 'Interface' : 'Class',
        range: {
          startLineNumber: lineNum,
          startColumn: 1,
          endLineNumber: lines.length,
          endColumn: line.length
        },
        children: []
      }
      symbols.push(currentClass)
      classBraceDepth = braceDepth
    }

    // 3. Methods & Functions
    let funcName: string | null = null
    let isMethod = Boolean(currentClass)

    if (isPy) {
      const pyMatch = line.match(/^\s*(?:async\s+)?def\s+([a-zA-Z0-9_]+)\s*\(/)
      if (pyMatch) funcName = pyMatch[1]
    } else {
      const phpJsMatch = line.match(
        /(?:(?:public|protected|private|static|async)\s+)*function\s+(?:&\s*)?([a-zA-Z0-9_]+)\s*\(/i
      )
      if (phpJsMatch) {
        funcName = phpJsMatch[1]
      } else if (currentClass) {
        const methodMatch = line.match(
          /^\s*(?:(?:public|protected|private|static|async|get|set)\s+)*([a-zA-Z0-9_]+)\s*\([^)]*\)\s*\{/
        )
        if (
          methodMatch &&
          !['if', 'for', 'while', 'switch', 'catch'].includes(methodMatch[1])
        ) {
          funcName = methodMatch[1]
        }
      } else {
        const arrowMatch = line.match(
          /(?:const|let|var|export\s+const)\s+([a-zA-Z0-9_]+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[a-zA-Z0-9_]+)\s*=>/
        )
        if (arrowMatch) {
          funcName = arrowMatch[1]
          isMethod = false
        }
      }
    }

    if (funcName) {
      const fnSym: DocumentOutlineSymbol = {
        id: `fn_${++symIdCounter}`,
        name: funcName,
        kind: isMethod ? 'Method' : 'Function',
        range: {
          startLineNumber: lineNum,
          startColumn: 1,
          endLineNumber: lineNum + 10,
          endColumn: line.length
        }
      }
      if (currentClass && currentClass.children) {
        if (currentClass.children.length > 0) {
          currentClass.children[currentClass.children.length - 1].range.endLineNumber = lineNum - 1
        }
        currentClass.children.push(fnSym)
      } else {
        if (symbols.length > 0) {
          symbols[symbols.length - 1].range.endLineNumber = lineNum - 1
        }
        symbols.push(fnSym)
      }
    }

    // Brace tracking
    const openBraces = (line.match(/\{/g) || []).length
    const closeBraces = (line.match(/\}/g) || []).length
    braceDepth += openBraces - closeBraces

    if (currentClass && braceDepth <= classBraceDepth && closeBraces > 0) {
      currentClass.range.endLineNumber = lineNum
      currentClass = null
    }
  }

  return symbols
}
