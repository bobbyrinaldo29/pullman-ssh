export interface PhpSuggestion {
  label: string
  kind: 'keyword' | 'function' | 'variable' | 'class' | 'snippet' | 'constant'
  detail: string
  documentation?: string
  insertText: string
  cursorOffset?: number // relative to insertion end
}

export const PHP_KEYWORDS: PhpSuggestion[] = [
  { label: 'function', kind: 'keyword', detail: 'keyword', insertText: 'function ' },
  { label: 'public', kind: 'keyword', detail: 'keyword', insertText: 'public ' },
  { label: 'private', kind: 'keyword', detail: 'keyword', insertText: 'private ' },
  { label: 'protected', kind: 'keyword', detail: 'keyword', insertText: 'protected ' },
  { label: 'static', kind: 'keyword', detail: 'keyword', insertText: 'static ' },
  { label: 'class', kind: 'keyword', detail: 'keyword', insertText: 'class ' },
  { label: 'interface', kind: 'keyword', detail: 'keyword', insertText: 'interface ' },
  { label: 'trait', kind: 'keyword', detail: 'keyword', insertText: 'trait ' },
  { label: 'extends', kind: 'keyword', detail: 'keyword', insertText: 'extends ' },
  { label: 'implements', kind: 'keyword', detail: 'keyword', insertText: 'implements ' },
  { label: 'namespace', kind: 'keyword', detail: 'keyword', insertText: 'namespace ' },
  { label: 'use', kind: 'keyword', detail: 'keyword', insertText: 'use ' },
  { label: 'return', kind: 'keyword', detail: 'keyword', insertText: 'return ' },
  { label: 'try', kind: 'keyword', detail: 'keyword', insertText: 'try ' },
  { label: 'catch', kind: 'keyword', detail: 'keyword', insertText: 'catch (\\Exception $e) ' },
  { label: 'finally', kind: 'keyword', detail: 'keyword', insertText: 'finally ' },
  { label: 'throw', kind: 'keyword', detail: 'keyword', insertText: 'throw new ' },
  { label: 'if', kind: 'keyword', detail: 'keyword', insertText: 'if ()', cursorOffset: -1 },
  { label: 'else', kind: 'keyword', detail: 'keyword', insertText: 'else ' },
  { label: 'elseif', kind: 'keyword', detail: 'keyword', insertText: 'elseif ()', cursorOffset: -1 },
  { label: 'foreach', kind: 'keyword', detail: 'keyword', insertText: 'foreach ($array as $item) ' },
  { label: 'while', kind: 'keyword', detail: 'keyword', insertText: 'while ()', cursorOffset: -1 },
  { label: 'switch', kind: 'keyword', detail: 'keyword', insertText: 'switch ()', cursorOffset: -1 },
  { label: 'case', kind: 'keyword', detail: 'keyword', insertText: 'case ' },
  { label: 'break', kind: 'keyword', detail: 'keyword', insertText: 'break;' },
  { label: 'continue', kind: 'keyword', detail: 'keyword', insertText: 'continue;' },
  { label: 'readonly', kind: 'keyword', detail: 'keyword', insertText: 'readonly ' },
  { label: 'final', kind: 'keyword', detail: 'keyword', insertText: 'final ' },
  { label: 'abstract', kind: 'keyword', detail: 'keyword', insertText: 'abstract ' },
  { label: 'match', kind: 'keyword', detail: 'keyword', insertText: 'match ()', cursorOffset: -1 },
  { label: 'echo', kind: 'keyword', detail: 'keyword', insertText: 'echo ' },
  { label: 'die', kind: 'keyword', detail: 'keyword', insertText: 'die();', cursorOffset: -2 },
  { label: 'exit', kind: 'keyword', detail: 'keyword', insertText: 'exit();', cursorOffset: -2 },
  { label: 'include', kind: 'keyword', detail: 'keyword', insertText: "include '';", cursorOffset: -2 },
  { label: 'include_once', kind: 'keyword', detail: 'keyword', insertText: "include_once '';", cursorOffset: -2 },
  { label: 'require', kind: 'keyword', detail: 'keyword', insertText: "require '';", cursorOffset: -2 },
  { label: 'require_once', kind: 'keyword', detail: 'keyword', insertText: "require_once '';", cursorOffset: -2 }
]

export const PHP_SUPERGLOBALS: PhpSuggestion[] = [
  { label: '$_GET', kind: 'variable', detail: 'array', documentation: 'An associative array of variables passed to the current script via the URL parameters.', insertText: '$_GET' },
  { label: '$_POST', kind: 'variable', detail: 'array', documentation: 'An associative array of variables passed to the current script via the HTTP POST method.', insertText: '$_POST' },
  { label: '$_SESSION', kind: 'variable', detail: 'array', documentation: 'An associative array containing session variables available to the current script.', insertText: '$_SESSION' },
  { label: '$_SERVER', kind: 'variable', detail: 'array', documentation: 'Array containing information such as headers, paths, and script locations.', insertText: '$_SERVER' },
  { label: '$_COOKIE', kind: 'variable', detail: 'array', documentation: 'An associative array of variables passed to the current script via HTTP Cookies.', insertText: '$_COOKIE' },
  { label: '$_REQUEST', kind: 'variable', detail: 'array', documentation: 'An associative array that by default contains the contents of $_GET, $_POST and $_COOKIE.', insertText: '$_REQUEST' },
  { label: '$_FILES', kind: 'variable', detail: 'array', documentation: 'An associative array of items uploaded to the current script via the HTTP POST method.', insertText: '$_FILES' },
  { label: '$_ENV', kind: 'variable', detail: 'array', documentation: 'An associative array of variables passed to the current script via the environment method.', insertText: '$_ENV' },
  { label: '$GLOBALS', kind: 'variable', detail: 'array', documentation: 'References all variables available in global scope.', insertText: '$GLOBALS' }
]

export const PHP_SNIPPETS: PhpSuggestion[] = [
  {
    label: '<?php',
    kind: 'snippet',
    detail: 'PHP open tag',
    documentation: 'Standard PHP opening tag',
    insertText: '<?php\n\n'
  },
  {
    label: 'pubf',
    kind: 'snippet',
    detail: 'public function ...()',
    documentation: 'Insert a public method skeleton',
    insertText: 'public function name($params): void\n{\n    // TODO: implement\n}\n'
  },
  {
    label: 'prif',
    kind: 'snippet',
    detail: 'private function ...()',
    documentation: 'Insert a private method skeleton',
    insertText: 'private function name($params): void\n{\n    // TODO: implement\n}\n'
  },
  {
    label: 'prof',
    kind: 'snippet',
    detail: 'protected function ...()',
    documentation: 'Insert a protected method skeleton',
    insertText: 'protected function name($params): void\n{\n    // TODO: implement\n}\n'
  },
  {
    label: 'construct',
    kind: 'snippet',
    detail: 'public function __construct()',
    documentation: 'Constructor method',
    insertText: 'public function __construct()\n{\n    \n}\n'
  },
  {
    label: 'class_skeleton',
    kind: 'snippet',
    detail: 'class Definition',
    documentation: 'Complete PHP Class with constructor',
    insertText: 'class Name\n{\n    public function __construct()\n    {\n        \n    }\n}\n'
  },
  {
    label: 'trycatch',
    kind: 'snippet',
    detail: 'try { ... } catch (\\Throwable $e)',
    documentation: 'Try / Catch block with Exception handling',
    insertText: 'try {\n    \n} catch (\\Throwable $e) {\n    // log error: $e->getMessage()\n}\n'
  },
  {
    label: 'fore',
    kind: 'snippet',
    detail: 'foreach ($array as $item)',
    documentation: 'Loop through elements of an array',
    insertText: 'foreach ($items as $item) {\n    \n}\n'
  },
  {
    label: 'forek',
    kind: 'snippet',
    detail: 'foreach ($array as $key => $value)',
    documentation: 'Loop through key/value pairs of an array',
    insertText: 'foreach ($items as $key => $value) {\n    \n}\n'
  }
]

export const PHP_FUNCTIONS: PhpSuggestion[] = [
  // Array Functions
  {
    label: 'array_merge',
    kind: 'function',
    detail: 'array_merge(array ...$arrays): array',
    documentation: 'Merge one or more arrays sequentially into a single array.',
    insertText: 'array_merge($array1, $array2)',
    cursorOffset: -1
  },
  {
    label: 'array_map',
    kind: 'function',
    detail: 'array_map(?callable $callback, array $array, array ...$arrays): array',
    documentation: 'Applies the callback to the elements of the given arrays.',
    insertText: 'array_map(function ($item) {\n    return $item;\n}, $array)',
    cursorOffset: -1
  },
  {
    label: 'array_filter',
    kind: 'function',
    detail: 'array_filter(array $array, ?callable $callback = null, int $mode = 0): array',
    documentation: 'Filters elements of an array using a callback function.',
    insertText: 'array_filter($array, function ($item) {\n    return !empty($item);\n})',
    cursorOffset: -1
  },
  {
    label: 'array_keys',
    kind: 'function',
    detail: 'array_keys(array $array): array',
    documentation: 'Return all the keys or a subset of the keys of an array.',
    insertText: 'array_keys($array)'
  },
  {
    label: 'array_values',
    kind: 'function',
    detail: 'array_values(array $array): array',
    documentation: 'Return all the values of an array indexed numerically.',
    insertText: 'array_values($array)'
  },
  {
    label: 'in_array',
    kind: 'function',
    detail: 'in_array(mixed $needle, array $haystack, bool $strict = false): bool',
    documentation: 'Checks if a value exists in an array.',
    insertText: 'in_array($needle, $haystack)'
  },
  {
    label: 'array_key_exists',
    kind: 'function',
    detail: 'array_key_exists(string|int $key, array $array): bool',
    documentation: 'Checks if the given key or index exists in the array.',
    insertText: 'array_key_exists($key, $array)'
  },
  {
    label: 'count',
    kind: 'function',
    detail: 'count(Countable|array $value, int $mode = COUNT_NORMAL): int',
    documentation: 'Counts all elements in an array or in a Countable object.',
    insertText: 'count($array)'
  },
  {
    label: 'array_push',
    kind: 'function',
    detail: 'array_push(array &$array, mixed ...$values): int',
    documentation: 'Push one or more elements onto the end of array.',
    insertText: 'array_push($array, $val)'
  },
  {
    label: 'array_pop',
    kind: 'function',
    detail: 'array_pop(array &$array): mixed',
    documentation: 'Pop the element off the end of array.',
    insertText: 'array_pop($array)'
  },
  {
    label: 'array_shift',
    kind: 'function',
    detail: 'array_shift(array &$array): mixed',
    documentation: 'Shift an element off the beginning of array.',
    insertText: 'array_shift($array)'
  },
  {
    label: 'array_unshift',
    kind: 'function',
    detail: 'array_unshift(array &$array, mixed ...$values): int',
    documentation: 'Prepend one or more elements to the beginning of an array.',
    insertText: 'array_unshift($array, $val)'
  },
  {
    label: 'array_slice',
    kind: 'function',
    detail: 'array_slice(array $array, int $offset, ?int $length = null): array',
    documentation: 'Extract a slice of the array.',
    insertText: 'array_slice($array, 0, 10)'
  },
  {
    label: 'array_splice',
    kind: 'function',
    detail: 'array_splice(array &$array, int $offset, ?int $length = null, mixed $replacement = []): array',
    documentation: 'Remove a portion of the array and replace it with something else.',
    insertText: 'array_splice($array, $offset, $length)'
  },
  {
    label: 'array_unique',
    kind: 'function',
    detail: 'array_unique(array $array, int $flags = SORT_STRING): array',
    documentation: 'Removes duplicate values from an array.',
    insertText: 'array_unique($array)'
  },
  {
    label: 'array_column',
    kind: 'function',
    detail: 'array_column(array $array, int|string|null $column_key, int|string|null $index_key = null): array',
    documentation: 'Return the values from a single column in the input array.',
    insertText: "array_column($array, 'column_name')"
  },

  // String Functions
  {
    label: 'strlen',
    kind: 'function',
    detail: 'strlen(string $string): int',
    documentation: 'Get string length in bytes.',
    insertText: 'strlen($str)'
  },
  {
    label: 'strpos',
    kind: 'function',
    detail: 'strpos(string $haystack, string $needle, int $offset = 0): int|false',
    documentation: 'Find the numeric position of the first occurrence of a substring.',
    insertText: 'strpos($haystack, $needle)'
  },
  {
    label: 'substr',
    kind: 'function',
    detail: 'substr(string $string, int $offset, ?int $length = null): string',
    documentation: 'Return part of a string starting at offset.',
    insertText: 'substr($string, 0, 10)'
  },
  {
    label: 'str_replace',
    kind: 'function',
    detail: 'str_replace(array|string $search, array|string $replace, string|array $subject): string|array',
    documentation: 'Replace all occurrences of the search string with the replacement string.',
    insertText: "str_replace($search, $replace, $subject)"
  },
  {
    label: 'explode',
    kind: 'function',
    detail: 'explode(string $separator, string $string, int $limit = PHP_INT_MAX): array',
    documentation: 'Split a string by a string delimiter into an array.',
    insertText: "explode(',', $string)"
  },
  {
    label: 'implode',
    kind: 'function',
    detail: 'implode(string $separator, array $array): string',
    documentation: 'Join array elements with a string glue.',
    insertText: "implode(', ', $array)"
  },
  {
    label: 'trim',
    kind: 'function',
    detail: 'trim(string $string, string $characters = " \\n\\r\\t\\v\\x00"): string',
    documentation: 'Strip whitespace (or other characters) from the beginning and end of a string.',
    insertText: 'trim($string)'
  },
  {
    label: 'strtolower',
    kind: 'function',
    detail: 'strtolower(string $string): string',
    documentation: 'Make a string lowercase.',
    insertText: 'strtolower($string)'
  },
  {
    label: 'strtoupper',
    kind: 'function',
    detail: 'strtoupper(string $string): string',
    documentation: 'Make a string uppercase.',
    insertText: 'strtoupper($string)'
  },
  {
    label: 'str_contains',
    kind: 'function',
    detail: 'str_contains(string $haystack, string $needle): bool',
    documentation: 'Determine if a string contains a given substring (PHP 8.0+).',
    insertText: 'str_contains($haystack, $needle)'
  },
  {
    label: 'str_starts_with',
    kind: 'function',
    detail: 'str_starts_with(string $haystack, string $needle): bool',
    documentation: 'Checks if a string starts with a given substring (PHP 8.0+).',
    insertText: 'str_starts_with($haystack, $needle)'
  },
  {
    label: 'str_ends_with',
    kind: 'function',
    detail: 'str_ends_with(string $haystack, string $needle): bool',
    documentation: 'Checks if a string ends with a given substring (PHP 8.0+).',
    insertText: 'str_ends_with($haystack, $needle)'
  },
  {
    label: 'sprintf',
    kind: 'function',
    detail: 'sprintf(string $format, mixed ...$values): string',
    documentation: 'Return a formatted string according to format directives.',
    insertText: "sprintf('%s: %d', $label, $count)"
  },

  // JSON & Serialization
  {
    label: 'json_encode',
    kind: 'function',
    detail: 'json_encode(mixed $value, int $flags = 0, int $depth = 512): string|false',
    documentation: 'Returns the JSON representation of a value.',
    insertText: 'json_encode($data, JSON_PRETTY_PRINT)'
  },
  {
    label: 'json_decode',
    kind: 'function',
    detail: 'json_decode(string $json, ?bool $associative = null, int $depth = 512, int $flags = 0): mixed',
    documentation: 'Takes a JSON encoded string and converts it into a PHP variable.',
    insertText: 'json_decode($json, true)'
  },

  // Variable & Type Checking
  {
    label: 'isset',
    kind: 'function',
    detail: 'isset(mixed $var, mixed ...$vars): bool',
    documentation: 'Determine if a variable is declared and is different than null.',
    insertText: 'isset($var)'
  },
  {
    label: 'empty',
    kind: 'function',
    detail: 'empty(mixed $var): bool',
    documentation: 'Determine whether a variable is considered empty.',
    insertText: 'empty($var)'
  },
  {
    label: 'is_null',
    kind: 'function',
    detail: 'is_null(mixed $value): bool',
    documentation: 'Finds whether a variable is null.',
    insertText: 'is_null($value)'
  },
  {
    label: 'is_array',
    kind: 'function',
    detail: 'is_array(mixed $value): bool',
    documentation: 'Finds whether a variable is an array.',
    insertText: 'is_array($value)'
  },
  {
    label: 'is_string',
    kind: 'function',
    detail: 'is_string(mixed $value): bool',
    documentation: 'Find whether a variable is a string.',
    insertText: 'is_string($value)'
  },
  {
    label: 'is_numeric',
    kind: 'function',
    detail: 'is_numeric(mixed $value): bool',
    documentation: 'Finds whether a variable is a number or a numeric string.',
    insertText: 'is_numeric($value)'
  },
  {
    label: 'var_dump',
    kind: 'function',
    detail: 'var_dump(mixed $value, mixed ...$values): void',
    documentation: 'Dumps information about one or more variables.',
    insertText: 'var_dump($var);'
  },
  {
    label: 'print_r',
    kind: 'function',
    detail: 'print_r(mixed $value, bool $return = false): string|bool',
    documentation: 'Prints human-readable information about a variable.',
    insertText: 'print_r($var, true)'
  },

  // Filesystem
  {
    label: 'file_get_contents',
    kind: 'function',
    detail: 'file_get_contents(string $filename): string|false',
    documentation: 'Reads entire file into a string.',
    insertText: "file_get_contents('/path/to/file')"
  },
  {
    label: 'file_put_contents',
    kind: 'function',
    detail: 'file_put_contents(string $filename, mixed $data, int $flags = 0): int|false',
    documentation: 'Write data to a file.',
    insertText: 'file_put_contents($path, $content)'
  },
  {
    label: 'file_exists',
    kind: 'function',
    detail: 'file_exists(string $filename): bool',
    documentation: 'Checks whether a file or directory exists.',
    insertText: 'file_exists($path)'
  },
  {
    label: 'unlink',
    kind: 'function',
    detail: 'unlink(string $filename): bool',
    documentation: 'Deletes a file from the filesystem.',
    insertText: 'unlink($path)'
  },

  // Date and Time
  {
    label: 'date',
    kind: 'function',
    detail: 'date(string $format, ?int $timestamp = null): string',
    documentation: 'Format a local time/date.',
    insertText: "date('Y-m-d H:i:s')"
  },
  {
    label: 'time',
    kind: 'function',
    detail: 'time(): int',
    documentation: 'Return current Unix timestamp.',
    insertText: 'time()'
  },
  {
    label: 'strtotime',
    kind: 'function',
    detail: 'strtotime(string $datetime, ?int $baseTimestamp = null): int|false',
    documentation: 'Parse about any English textual datetime description into a Unix timestamp.',
    insertText: "strtotime('+1 day')"
  },

  // Security & Passwords
  {
    label: 'password_hash',
    kind: 'function',
    detail: 'password_hash(string $password, string|int|null $algo, array $options = []): string',
    documentation: 'Creates a password hash using strong one-way hashing algorithm.',
    insertText: 'password_hash($password, PASSWORD_BCRYPT)'
  },
  {
    label: 'password_verify',
    kind: 'function',
    detail: 'password_verify(string $password, string $hash): bool',
    documentation: 'Verifies that a password matches a hash.',
    insertText: 'password_verify($password, $hash)'
  },

  // HTTP & Headers
  {
    label: 'header',
    kind: 'function',
    detail: 'header(string $header, bool $replace = true, int $response_code = 0): void',
    documentation: 'Send a raw HTTP header.',
    insertText: "header('Content-Type: application/json');"
  },
  {
    label: 'http_response_code',
    kind: 'function',
    detail: 'http_response_code(int $response_code = 0): int|bool',
    documentation: 'Get or Set the HTTP response code.',
    insertText: 'http_response_code(200)'
  }
]

