/** Text hyphenation in Javascript.
 *  Copyright (C) 2026 Yevhen Tiurin (yevhentiurin@gmail.com)
 *  https://github.com/ytiurin/hyphen
 *
 *  Released under the ISC license
 *  https://github.com/ytiurin/hyphen/blob/master/LICENSE
 */
(function (root, factory) {
  if (typeof define === "function" && define.amd) {
    // AMD. Register as an anonymous module.
    define([], factory);
  } else if (typeof module === "object" && module.exports) {
    // Node. Does not work with strict CommonJS, but
    // only CommonJS-like environments that support module.exports,
    // like Node.
    module.exports = factory();
  } else {
    // Browser globals (root is window)
    root.createHyphenator = factory();
  }
})(this, function () {
  function createTextReader(setup) {
    var char1 = "";
    var char2 = "";
    var i = 0;
    var verifier = setup();
    return function (text) {
      while (i < text.length) {
        char1 = text.charAt(i++);
        char2 = text.charAt(i);
        var verified = verifier(char1, char2);
        if (verified !== void 0) {
          return verified;
        }
      }
    };
  }

  var isNotLetter = RegExp.prototype.test.bind(
    /\s|(?![\'])[\!-\@\[-\`\{-\~\u2013-\u203C]/
  );
  function createHTMLVerifier() {
    var skip = false;
    return function (accumulate, chars) {
      if (skip) {
        if (chars[0] === ">") {
          accumulate();
          skip = false;
        }
      } else if (
        chars[0] === "<" &&
        (!isNotLetter(chars[1]) || chars[1] === "/")
      ) {
        skip = true;
      }
      return skip;
    };
  }
  function createHyphenCharVerifier(hyphenChar) {
    var skip = false;
    return function (accumulate, chars) {
      if (skip) {
        if (!isNotLetter(chars[0]) && isNotLetter(chars[1])) {
          accumulate();
          skip = false;
        }
      } else if (!isNotLetter(chars[0]) && chars[1] === hyphenChar) {
        skip = true;
      }
      return skip;
    };
  }
  function createHyphenationVerifier(verifiers, minWordLength) {
    return function () {
      var accum0 = "";
      var accum = "";
      function accumulate() {
        accum0 += accum;
        accum = "";
      }
      function resolveWith(value) {
        accum0 = "";
        accum = "";
        return value;
      }
      return function (char1, char2) {
        accum += char1;
        var skip = verifiers.reduce(function (skip2, verify) {
          return skip2 || verify(accumulate, [char1, char2]);
        }, false);
        if (!skip) {
          if (isNotLetter(char1) && !isNotLetter(char2)) {
            accumulate();
          }
          if (!isNotLetter(char1) && isNotLetter(char2)) {
            if (accum.length >= minWordLength) {
              return resolveWith([accum0, accum]);
            } else {
              accumulate();
            }
          }
        }
        if (char2 === "") {
          if (accum.length < minWordLength || skip) {
            accumulate();
          }
          return resolveWith([accum0, accum]);
        }
      };
    };
  }

  function levelsToMarkers(levels) {
    var markers = [];
    for (var i = 0; i < levels.length; i++)
      if ((levels[i] & 1) === 1) markers.push(i);
    return markers;
  }
  function insertChar(text, hyphenChar, markers) {
    if (markers.length === 0) {
      return text;
    }
    var resultText = [text.slice(0, markers[0])];
    if (markers.length > 1)
      for (var i = 0, j = 1; j < markers.length; i++, j++) {
        resultText.push(text.slice(markers[i], markers[j]));
      }
    resultText.push(text.slice(markers[markers.length - 1]));
    return resultText.join(hyphenChar);
  }
  function markersFromExceptionsDefinition(exceptionsList) {
    return exceptionsList.reduce(function (markersDict, definition) {
      var i = 0,
        markers = [];
      while ((i = definition.indexOf("-", i + 1)) > -1) {
        markers.push(i);
      }
      markersDict[definition.toLocaleLowerCase().replace(/\-/g, "")] = markers;
      return markersDict;
    }, {});
  }

  function createCharIterator(str) {
    var i = 0;
    function nextChar() {
      return str[i++];
    }
    return nextChar;
  }
  function createStringSlicer(str) {
    var i = 0,
      slice = str;
    function next() {
      slice = str.slice(i++);
      if (slice.length < 3) {
        return;
      }
      return slice;
    }
    function isFirstCharacter() {
      return i === 2;
    }
    return [next, isFirstCharacter];
  }
  function hyphenateWord(text, loweredText, levelsTable, patternTrie) {
    var levels = new Array(text.length + 1),
      loweredText = ("." + loweredText + ".").split(""),
      wordSlice,
      letter,
      triePtr,
      trieNode,
      patternLevelsIndex,
      patternLevels,
      patternEntityIndex = -1,
      slicer,
      nextSlice,
      isFirstCharacter,
      nextLetter;
    for (var i = levels.length; i--; ) levels[i] = 0;
    slicer = createStringSlicer(loweredText);
    nextSlice = slicer[0];
    isFirstCharacter = slicer[1];
    while ((wordSlice = nextSlice())) {
      patternEntityIndex++;
      if (isFirstCharacter()) {
        patternEntityIndex--;
      }
      triePtr = patternTrie;
      nextLetter = createCharIterator(wordSlice);
      while ((letter = nextLetter())) {
        if ((trieNode = triePtr[letter]) === void 0) {
          break;
        }
        triePtr = {};
        patternLevelsIndex = -1;
        switch (Object.prototype.toString.call(trieNode)) {
          case "[object Array]":
            triePtr = trieNode[0];
            patternLevelsIndex = trieNode[1];
            break;
          case "[object Object]":
            triePtr = trieNode;
            break;
          case "[object Number]":
            patternLevelsIndex = trieNode;
            break;
        }
        if (patternLevelsIndex < 0) {
          continue;
        }
        patternLevels = levelsTable[patternLevelsIndex];
        for (var k = 0; k < patternLevels.length; k++)
          levels[patternEntityIndex + k] = Math.max(
            patternLevels[k],
            levels[patternEntityIndex + k]
          );
      }
    }
    levels[0] = levels[1] = levels[levels.length - 1] = levels[
      levels.length - 2
    ] = 0;
    return levelsToMarkers(levels);
  }

  function start(
    text,
    levelsTable,
    patterns,
    cache,
    markersDict,
    hyphenChar,
    skipHTML,
    minWordLength,
    isAsync
  ) {
    function done() {
      resolveNewText(newText);
    }
    var newText = "",
      fragments,
      readText = createTextReader(
        createHyphenationVerifier(
          (skipHTML ? [createHTMLVerifier()] : []).concat(
            createHyphenCharVerifier(hyphenChar)
          ),
          minWordLength
        )
      ),
      resolveNewText = function () {};
    function nextTick() {
      var loopStart = /* @__PURE__ */ new Date();
      while (
        (!isAsync || /* @__PURE__ */ new Date() - loopStart < 10) &&
        (fragments = readText(text))
      ) {
        if (fragments[1]) {
          var cacheKey = fragments[1].length ? "~" + fragments[1] : "";
          if (!Object.prototype.hasOwnProperty.call(cache, cacheKey)) {
            var loweredWord = fragments[1].toLocaleLowerCase();
            if (!Object.prototype.hasOwnProperty.call(markersDict, loweredWord))
              markersDict[loweredWord] = hyphenateWord(
                fragments[1],
                loweredWord,
                levelsTable,
                patterns
              );
            cache[cacheKey] = insertChar(
              fragments[1],
              hyphenChar,
              markersDict[loweredWord]
            );
          }
          fragments[1] = cache[cacheKey];
        }
        newText += fragments[0] + fragments[1];
      }
      if (!fragments) {
        done();
      } else {
        setTimeout(nextTick);
      }
    }
    if (isAsync) {
      setTimeout(nextTick);
      return new Promise(function (resolve) {
        resolveNewText = resolve;
      });
    } else {
      nextTick();
      return newText;
    }
  }

  var SETTING_DEFAULT_ASYNC = false;
  var SETTING_DEFAULT_EXCEPTIONS = [];
  var SETTING_DEFAULT_HTML = true;
  var SETTING_DEFAULT_HYPH_CHAR = "\xAD";
  var SETTING_DEFAULT_MIN_WORD_LENGTH = 5;
  var SETTING_NAME_ASYNC = "async";
  var SETTING_NAME_EXCEPTIONS = "exceptions";
  var SETTING_NAME_HTML = "html";
  var SETTING_NAME_HYPH_CHAR = "hyphenChar";
  var SETTING_NAME_MIN_WORD_LENGTH = "minWordLength";
  var _global =
    typeof global === "object"
      ? global
      : typeof window === "object"
      ? window
      : typeof self === "object"
      ? self
      : false
      ? void 0
      : {};
  function extend(target, source) {
    target = target || {};
    for (var key in source) {
      target[key] = source[key];
    }
    return target;
  }
  function validateArray(value) {
    return value instanceof Array;
  }
  function keyOrDefault(object, key, defaultValue, test) {
    if (key in object && (test ? test(object[key]) : true)) {
      return object[key];
    }
    return defaultValue;
  }
  function exceptionsFromMarkers(markers, hyphenChar) {
    var exceptions = {};
    for (var word in markers) {
      exceptions["~" + word] = insertChar(word, hyphenChar, markers[word]);
    }
    return exceptions;
  }
  function exceptionsFromDefinition(exceptionsList, hyphenChar) {
    return exceptionsList.reduce(function (exceptions, exception) {
      exceptions["~" + exception.replace(/\-/g, "")] = exception.replace(
        /\-/g,
        hyphenChar
      );
      return exceptions;
    }, {});
  }
  function createHyphenator(patternsDefinition, options) {
    options = options || {};
    var asyncMode = keyOrDefault(
        options,
        SETTING_NAME_ASYNC,
        SETTING_DEFAULT_ASYNC
      ),
      caches = {},
      markersDict = {},
      exceptions = {},
      hyphenChar = keyOrDefault(
        options,
        SETTING_NAME_HYPH_CHAR,
        SETTING_DEFAULT_HYPH_CHAR
      ),
      levelsTable = patternsDefinition[0],
      patterns = patternsDefinition[1],
      minWordLength =
        keyOrDefault(
          options,
          SETTING_NAME_MIN_WORD_LENGTH,
          SETTING_DEFAULT_MIN_WORD_LENGTH
        ) >> 0,
      skipHTML = keyOrDefault(options, SETTING_NAME_HTML, SETTING_DEFAULT_HTML),
      userExceptions = keyOrDefault(
        options,
        SETTING_NAME_EXCEPTIONS,
        SETTING_DEFAULT_EXCEPTIONS,
        validateArray
      );
    var cacheKey = hyphenChar + minWordLength;
    exceptions[cacheKey] = {};
    if (patternsDefinition[2]) {
      exceptions[cacheKey] = exceptionsFromMarkers(
        patternsDefinition[2],
        hyphenChar
      );
      markersDict = patternsDefinition[2];
    }
    if (userExceptions && userExceptions.length) {
      exceptions[cacheKey] = extend(
        exceptions[cacheKey],
        exceptionsFromDefinition(userExceptions, hyphenChar)
      );
      markersDict = extend(
        markersDict,
        markersFromExceptionsDefinition(userExceptions)
      );
    }
    caches[cacheKey] = extend({}, exceptions[cacheKey]);
    if (asyncMode && !("Promise" in _global)) {
      throw new Error(
        "Failed to create hyphenator: Could not find global Promise object, needed for hyphenator to work in async mode"
      );
    }
    return function (text, options2) {
      options2 = options2 || {};
      var localHyphenChar = keyOrDefault(
          options2,
          SETTING_NAME_HYPH_CHAR,
          hyphenChar
        ),
        localMinWordLength =
          keyOrDefault(options2, SETTING_NAME_MIN_WORD_LENGTH, minWordLength) >>
          0,
        localUserExceptions = keyOrDefault(
          options2,
          SETTING_NAME_EXCEPTIONS,
          SETTING_DEFAULT_EXCEPTIONS,
          validateArray
        ),
        cacheKey2 = localHyphenChar + localMinWordLength;
      if (!exceptions[cacheKey2] && patternsDefinition[2]) {
        exceptions[cacheKey2] = exceptionsFromMarkers(
          patternsDefinition[2],
          localHyphenChar
        );
        caches[cacheKey2] = extend(caches[cacheKey2], exceptions[cacheKey2]);
      }
      if (localUserExceptions && localUserExceptions.length) {
        exceptions[cacheKey2] = extend(
          exceptions[cacheKey2],
          exceptionsFromDefinition(localUserExceptions, localHyphenChar)
        );
        markersDict = extend(
          markersDict,
          markersFromExceptionsDefinition(localUserExceptions)
        );
        caches[cacheKey2] = extend(caches[cacheKey2], exceptions[cacheKey2]);
      }
      return start(
        text,
        levelsTable,
        patterns,
        caches[cacheKey2],
        markersDict,
        localHyphenChar,
        skipHTML,
        localMinWordLength,
        asyncMode
      );
    };
  }

  return createHyphenator;
});

(function (root, exports) {
  if (typeof define === "function" && define.amd) {
    // AMD. Register as an anonymous module.
    define([], function () {
      return exports;
    });
  } else if (typeof module === "object" && module.exports) {
    // Node. Does not work with strict CommonJS, but
    // only CommonJS-like environments that support module.exports,
    // like Node.
    module.exports = exports;
  } else {
    // Browser globals (root is window)
    root.hyphenationPatternsFr = exports;
  }
})(this, [
  [
    [2, 2],
    [0, 4],
    [0, 0, 4],
    [0, 0, 2],
    [0, 0, 3],
    [0, 0, 0, 3],
    [0, 1, 2],
    [0, 0, 3, 4],
    [0, 0, 0, 3, 4],
    [1],
    [0, 2],
    [0, 2, 1],
    [0, 0, 0, 0, 0, 1, 2],
    [0, 0, 0, 0, 0, 0, 1, 2],
    [0, 0, 0, 0, 3, 4],
    [1, 2],
    [0, 2, 2],
    [0, 0, 0, 0, 1, 2],
    [0, 0, 0, 0, 2],
    [0, 0, 0, 0, 0, 2],
    [0, 0, 0, 2, 3],
    [0, 0, 0, 0, 2, 3],
    [0, 0, 0, 2],
    [0, 2, 3],
    [0, 0, 0, 2, 0, 3],
    [4],
    [2],
    [0, 0, 1, 2],
    [0, 0, 1],
    [0, 0, 0, 1, 2],
    [0, 0, 2, 1, 2],
    [0, 0, 3, 0, 3, 2],
    [0, 3],
    [0, 0, 0, 0, 0, 0, 3],
    [0, 0, 0, 0, 3],
    [0, 0, 0, 0, 0, 0, 0, 0, 3],
    [0, 0, 0, 0, 0, 0, 0, 4],
    [0, 0, 0, 0, 0, 4],
    [0, 0, 0, 2, 0, 0, 3],
    [0, 0, 0, 0, 2, 3, 2],
    [0, 0, 2, 1],
    [2, 0, 3],
    [0, 0, 0, 4],
    [0, 0, 0, 0, 4],
    [0, 0, 2, 3],
    [0, 0, 0, 0, 0, 3],
    [0, 0, 3, 2, 3],
    [0, 0, 3, 2],
    [3, 2],
    [0, 2, 1, 2],
    [0, 0, 0, 2, 1, 2],
    [0, 0, 0, 0, 0, 1],
    [0, 0, 0, 0, 0, 0, 0, 3],
    [0, 0, 0, 0, 1],
    [0, 0, 0, 0, 0, 0, 2],
    [0, 0, 0, 0, 4, 1],
    [0, 1],
    [0, 0, 0, 0, 0, 5],
    [0, 0, 0, 0, 0, 0, 4],
    [0, 0, 0, 0, 0, 4, 3],
    [0, 0, 0, 0, 0, 0, 0, 2],
    [0, 0, 0, 0, 4, 3],
    [0, 0, 0, 0, 0, 0, 0, 0, 2],
    [0, 0, 0, 0, 2, 1, 2],
    [0, 3, 2],
    [0, 0, 0, 0, 0, 2, 3],
    [0, 0, 0, 1],
    [0, 0, 1, 2, 2],
    [0, 0, 0, 0, 0, 0, 3, 2],
    [3, 0, 2],
    [0, 0, 0, 2, 1],
    [0, 0, 0, 0, 3, 2],
    [0, 0, 4, 5],
    [2, 3],
    [0, 0, 0, 0, 0, 3, 2]
  ],
  {
    "'": [
      {
        a: [
          {
            b: { r: { é: { a: 5 } } },
            e: { s: { c: { h: 8 } } },
            l: { c: { o: { o: { l: 10 } } } },
            m: { i: { n: { o: { a: { c: 13 } } } } },
            n: {
              a: { s: { t: { r: 14 } } },
              e: { s: { t: { h: { é: { s: { i: 16 } } } } } },
              t: {
                i: { a: 12, e: [{ n: { n: { e: 19 } } }, 12], é: 12, s: 12 }
              }
            },
            p: { o: { s: { t: { a: 21 } } } },
            s: { t: { a: 22 } },
            r: {
              g: { e: { n: { t: { ".": 5 } } } },
              p: { e: { n: { t: { ".": 5 } } } }
            },
            g: { n: { a: { t: 44 } } }
          },
          2
        ],
        â: 2,
        e: [{ n: { a: 29, o: 29 }, u: { r: { a: 50 } } }, 2],
        ê: 2,
        é: 2,
        è: 2,
        i: [
          {
            g: { n: { é: 44, i: 44 } },
            n: {
              f: { o: { r: { m: { a: { t: 10 } } } } },
              a: [{ n: { i: { t: 20 } }, u: { g: { u: { r: 22 } } } }, 29],
              e: [
                {
                  f: { f: { a: { b: 22 } } },
                  p: { t: 22 },
                  r: 22,
                  x: { o: { r: { a: 22 } } }
                },
                29
              ],
              é: [
                {
                  l: { u: { c: { t: { a: 20 } } } },
                  n: { a: { r: { r: { a: 20 } } } }
                },
                29
              ],
              i: [{ m: { i: { t: { i: 20 } } }, q: 20, t: 20 }, 29],
              o: [{ c: { u: { l: 20 } }, n: { d: 22 } }, 29],
              s: { t: { a: { b: 29 } } },
              t: {
                e: {
                  r: [{ a: 60, e: 60, é: 60, i: 60, o: 60, u: 60, s: 60 }, 59]
                }
              },
              u: [{ i: { t: 22 }, l: 20 }, 29]
            }
          },
          2
        ],
        o: [
          {
            n: { g: { u: { e: { n: { t: { ".": 5 } } } } } },
            c: { t: { e: { t: 10 } } },
            u: { a: { o: { u: 53 } } },
            v: { i: { s: { c: 17 } } }
          },
          2
        ],
        î: 2,
        ô: 2,
        u: 2,
        û: 2,
        y: 2
      },
      0
    ],
    ".": {
      a: [
        {
          b: { r: { é: { a: 4 } } },
          e: { s: { c: { h: 7 } } },
          m: { i: { n: { o: { a: { c: 12 } } } } },
          n: {
            a: { s: { t: { r: 8 } } },
            t: { i: { a: 17, e: [{ n: { n: { e: 18 } } }, 17], é: 17, s: 17 } }
          },
          p: { o: { s: { t: { a: 20 } } } },
          s: { t: { a: 3 } },
          r: {
            d: { e: { n: { t: { ".": 4 } } } },
            g: { e: { n: { t: { ".": 4 } } } },
            p: { e: { n: { t: { ".": 4 } } } }
          },
          g: { n: { a: { t: 23 } } }
        },
        1
      ],
      â: 1,
      b: {
        a: { i: { s: { e: { m: { a: { i: { n: 24 } } } } } } },
        i: { a: { c: 27, t: 27, u: 28 }, o: { a: 29 }, s: { a: 30 }, u: 27 }
      },
      c: {
        h: [
          {
            è: {
              v: {
                r: { e: { f: { e: { u: { i: { l: { l: { e: 38 } } } } } } } }
              }
            }
          },
          2
        ],
        i: { s: { a: { l: { p: 40 } } } },
        o: {
          n: [
            {
              s: 43,
              t: {
                r: {
                  e: { s: { c: 13 }, m: { a: { î: { t: { r: { e: 33 } } } } } }
                }
              }
            },
            42
          ],
          o: [{ l: { i: { e: 44 } } }, 27],
          m: { m: { e: { n: { t: { ".": 5 } } } } }
        },
        u: { l: 42 }
      },
      d: {
        a: { c: { r: { y: { o: { a: 13 } } } } },
        é: {
          a: 27,
          i: { o: 28 },
          o: 27,
          s: [
            {
              a: {
                c: { r: 46 },
                m: 20,
                t: { e: { l: { l: 46 } } },
                s: { t: { r: 47 } }
              },
              c: 47,
              é: [{ g: { r: 46 } }, 30],
              e: { n: { s: { i: { b: 47 } } }, r: { t: 47 }, x: { u: 47 } },
              i: [
                {
                  d: 46,
                  g: { n: 46 },
                  l: { i: 46 },
                  n: { e: { n: 46 }, v: { o: 47 } },
                  r: 46,
                  s: { t: 47 }
                },
                30
              ],
              o: {
                d: { é: 46 },
                l: 46,
                p: { i: { l: 46 } },
                r: { m: 47, p: 47 },
                u: { f: { r: 47 } }
              },
              œ: 40,
              p: 47,
              t: 47,
              u: { n: 30 }
            },
            3
          ]
        },
        i: {
          a: {
            c: { é: 27, i: { d: 27 } },
            l: { d: 28 },
            m: { i: 27 },
            t: { o: { m: 27 } }
          },
          e: { n: 27 },
          s: { h: 44 }
        },
        y: { s: [{ a: 30, i: 30, o: 30, u: 30 }, 44] },
        o: { l: { e: { n: { t: { ".": 4 } } } } }
      },
      e: [{ n: { a: 27, o: 27 }, u: { r: { a: 30 } } }, 1],
      ê: 1,
      é: [{ m: { i: { n: { e: { n: { t: { ".": 5 } } } } } } }, 1],
      è: 1,
      i: [
        {
          g: { n: { é: 23, i: 23 } },
          n: {
            a: [{ n: { i: { t: 44 } }, u: { g: { u: { r: 3 } } } }, 27],
            e: [
              {
                f: { f: { a: { b: 3 } } },
                p: { t: 3 },
                r: 3,
                x: { o: { r: { a: 3 } } }
              },
              27
            ],
            é: [
              {
                l: { u: { c: { t: { a: 44 } } } },
                n: { a: { r: { r: { a: 44 } } } }
              },
              27
            ],
            i: [{ m: { i: { t: { i: 44 } } }, q: 44, t: 44 }, 27],
            o: [{ c: { u: { l: 44 } }, n: { d: 3 } }, 27],
            s: { t: { a: { b: 27 } } },
            t: {
              e: {
                r: [{ a: 54, e: 54, é: 54, i: 54, o: 54, u: 54, s: 54 }, 61]
              }
            },
            u: [{ i: { t: 3 }, l: 44 }, 27]
          }
        },
        1
      ],
      m: {
        a: {
          g: {
            n: {
              i: {
                c: { i: { d: { e: 44 } } },
                f: { i: { c: { a: { t: 44 } } } }
              },
              u: { m: 44 }
            }
          },
          c: { k: 44, r: { o: { s: { c: 12 } } } },
          l: {
            a: {
              d: { r: { e: { s: 30 }, o: 30 } },
              i: { s: { é: 40 } },
              p: 40,
              v: 30
            },
            e: { n: 40 },
            i: { n: { t: 40 } },
            o: { c: 40, d: 30 }
          },
          r: { x: 40 }
        },
        é: {
          g: { o: { h: 40 } },
          s: { a: [{ n: 4 }, 3], e: { s: 40 }, i: 40, u: { s: 30 } },
          t: { a: { s: { t: { a: 17 } } } }
        },
        i: { l: { l: { i: { a: { m: 51 } } } } },
        o: {
          n: {
            o: {
              a: 17,
              e: 17,
              é: 17,
              i: 17,
              ï: { d: { é: 17 } },
              o: 17,
              u: 17,
              s: 17
            }
          }
        }
      },
      p: {
        r: {
          o: {
            g: { n: { a: { t: { h: 20 } } } },
            é: 29,
            s: { c: { é: 29 } },
            u: { d: { h: 71 } }
          },
          é: {
            a: [{ l: { a: 20 }, u: 22 }, 29],
            é: 29,
            e: 29,
            i: 29,
            o: 29,
            u: 29,
            s: 29
          }
        },
        a: {
          n: {
            a: { f: 30, m: { é: 30 }, r: { a: 30 } },
            i: { s: 40 },
            o: { p: { h: 30, t: 40 } }
          },
          r: {
            a: { c: { h: { e: 30, è: 30 } }, s: 17 },
            h: { é: 44 },
            e: { n: { t: { ".": 4 } } }
          },
          t: { e: { n: { t: { ".": 4 } } } }
        },
        e: {
          n: { t: { a: 22 } },
          r: [{ a: 29, e: 29, é: 29, i: 29, o: 29, u: 29 }, 2]
        },
        é: {
          r: { i: { o: { s: 53 }, s: [{ s: 21, t: { a: 21 } }, 17], u: 17 } }
        },
        h: [{ a: { l: { a: { n: { s: { t: 68 } } } } } }, 2],
        l: { u: { r: { i: { a: 51 } } } },
        o: {
          n: { t: { e: { t: 22 } } },
          s: { t: { h: 20, i: { n: 70 }, o: 50, r: 20, s: 17 } }
        },
        s: { y: { c: { h: { o: { a: { n: 13 } } } } } },
        u: { d: { d: { l: 29 } } }
      },
      s: {
        t: { a: { g: { n: 20 } }, i: { l: { l: 34 } } },
        y: { n: { g: { n: { a: { t: { h: 20 } } } } } },
        a: { r: { m: { e: { n: { t: { ".": 5 } } } } } },
        e: { r: { m: { e: { n: { t: { ".": 5 } } } } }, u: { l: { e: 22 } } },
        c: { h: 42 },
        h: 2,
        u: {
          b: {
            a: [{ l: { t: 47 } }, 30],
            é: [{ r: 46 }, 30],
            i: { n: 40 },
            l: { i: { m: { i: { n: 44 } }, n: 44 }, u: 44 },
            u: { r: 40 }
          },
          r: {
            a: [{ t: 46 }, 30],
            e: [{ a: { u: 47 }, l: { l: 47 }, t: 47 }, 30],
            é: 30,
            h: 44,
            i: { m: 30, n: { f: 40, t: 40 } },
            o: { f: 40, x: 40 }
          }
        },
        o: { u: { v: { e: { n: { t: { ".": 5 } } } } } }
      },
      o: [
        {
          n: { g: { u: { e: { n: { t: { ".": 4 } } } } } },
          u: { a: { o: { u: 66 } } },
          v: { i: { s: { c: 29 } } }
        },
        1
      ],
      î: 1,
      k: { h: 2 },
      t: {
        a: { l: { e: { n: { t: { ".": 4 } } } } },
        h: 2,
        r: { i: { a: { c: 29, n: 29, t: 29 }, o: { n: 29 } } }
      },
      g: { e: { m: { m: { e: { n: { t: { ".": 22 } } } } } } },
      n: { o: { n: { o: { b: { s: 40 } } } } },
      ô: 1,
      r: {
        é: {
          a: [{ l: { e: 44, i: { s: 44, t: 44 } }, u: { x: 3 } }, 27],
          é: 27,
          e: [{ l: 3, r: 3 }, 27],
          è: { r: 3 },
          i: [{ f: { i: 44 } }, 27],
          o: 27,
          u: [{ s: { s: 3 } }, 22],
          t: { r: { o: { a: 12 } } }
        },
        e: {
          s: [
            {
              c: {
                a: { p: 44 },
                i: { s: { i: 44, o: 44 } },
                o: { u: 44 },
                r: { i: 44 }
              },
              p: {
                e: { c: { t: 44 } },
                i: { r: 44 },
                l: { e: { n: { d: 44 } } },
                o: { n: { s: 44 } }
              },
              q: { u: { i: { l: 44 } } },
              s: [{ e: { n: { t: { ".": 5 } } } }, 44],
              t: [
                {
                  a: { b: 7, g: 7, n: { d: 7 }, t: 7 },
                  é: { n: 7, r: 7 },
                  i: { m: 7, p: 7 },
                  o: { c: 7, p: 7 },
                  r: [{ e: { i: { n: 72 } }, i: { c: { t: 72 }, n: 72 } }, 7],
                  u: 7,
                  y: 7
                },
                44
              ]
            },
            27
          ]
        }
      },
      l: { a: { t: { e: { n: { t: { ".": 4 } } } } } },
      u: 1,
      û: 1,
      y: 1
    },
    a: {
      b: {
        h: 3,
        î: { m: { e: { n: { t: { ".": 22 } } } } },
        s: {
          t: { i: { n: { e: { n: { t: { ".": 45 } } } } } },
          e: { n: { t: { ".": 4 } } }
        }
      },
      d: { h: 3 },
      è: { d: { r: { e: 6 } } },
      l: { c: { o: { o: { l: 9 } } }, a: { l: { g: { i: 11 } } } },
      n: {
        e: { s: { t: { h: { é: { s: { i: 15 } } } } } },
        i: { m: { e: { n: { t: { ".": 22 } } } } },
        t: { i: { f: { e: { r: { m: { e: { n: { t: { ".": 52 } } } } } } } } }
      },
      p: {
        o: { s: { t: { r: 20 } } },
        p: { a: { r: { e: { n: { t: { ".": 34 } } } } } }
      },
      r: {
        c: { h: { i: { é: { p: { i: { s: 12 } } } } } },
        m: { i: { l: { l: 57 } }, e: { n: { t: { ".": 3 } } } }
      },
      s: { t: { r: { o: 23 } }, m: { e: { n: { t: { ".": 3 } } } } },
      c: {
        c: { e: { n: { t: { ".": 4 } } } },
        q: { u: { i: { e: { s: { c: { e: { n: { t: { ".": 36 } } } } } } } } }
      },
      g: { n: { o: { s: 23 } } },
      v: { i: { l: { l: 43 } } },
      m: { a: { l: { g: { a: { m: { e: { n: { t: { ".": 54 } } } } } } } } },
      i: { m: { e: { n: { t: { ".": 3 } } } } },
      u: { m: { e: { n: { t: { ".": 3 } } } } }
    },
    b: {
      a: 9,
      â: 9,
      e: [{ ".": 25, s: { ".": 25 }, n: { t: { ".": 26 } } }, 9],
      é: 9,
      è: 9,
      ê: 9,
      i: 9,
      î: 9,
      l: [{ e: { ".": 25, s: { ".": 25 }, n: { t: { ".": 26 } } } }, 15],
      o: [
        {
          u: { t: { i: { l: { l: 33 } } }, m: { e: { n: { t: { ".": 22 } } } } }
        },
        9
      ],
      ô: 9,
      r: [
        {
          e: { ".": 25, s: { ".": 25 }, n: { t: { ".": 26 } } },
          u: { m: { e: { n: { t: { ".": 22 } } } } }
        },
        15
      ],
      u: 9,
      û: 9,
      y: 9
    },
    ç: 9,
    c: {
      a: [
        {
          o: { u: { t: 31 } },
          p: { i: { l: { l: 45 } } },
          r: { ê: { m: { e: { n: { t: { ".": 18 } } } } } }
        },
        9
      ],
      â: 9,
      e: [{ ".": 25, s: { ".": 25 }, n: { t: { ".": 26 } } }, 9],
      é: 9,
      è: 9,
      ê: 9,
      h: [
        {
          ".": 25,
          b: 26,
          e: {
            ".": 25,
            s: { ".": 25 },
            n: { t: { ".": 26 } },
            v: { i: { l: { l: 58 } } }
          },
          g: 26,
          l: [
            {
              e: { ".": 25, s: { ".": 25 } },
              o: { r: { a: { c: 39 }, é: { t: 39 } } }
            },
            3
          ],
          m: 26,
          n: 26,
          p: 26,
          r: [
            {
              e: { ".": 25, s: { ".": 25 } },
              o: { m: { e: { n: { t: { ".": 18 } } } } }
            },
            3
          ],
          s: 26,
          t: 26,
          w: 26,
          i: { e: { n: { d: { e: { n: { t: { ".": 45 } } } } } } }
        },
        15
      ],
      i: [{ l: { l: 5 } }, 9],
      î: 9,
      k: [
        {
          ".": 25,
          b: 26,
          e: { ".": 25, s: { ".": 25 }, n: { t: { ".": 26 } } },
          f: 26,
          g: 26,
          h: 41,
          p: 26,
          s: 26,
          t: 26
        },
        15
      ],
      l: [
        {
          e: { ".": 25, s: { ".": 25 }, n: { t: { ".": 26 } } },
          a: { m: { e: { n: { t: { ".": 22 } } } } }
        },
        15
      ],
      o: [
        {
          a: {
            c: { c: 28, q: 28 },
            d: 27,
            p: 28,
            r: 28,
            s: { s: { o: { c: 28 }, u: { r: 28 } } },
            u: 28,
            x: 28
          },
          é: 27,
          e: { f: 28, n: 28, x: 28 },
          n: {
            u: { r: { b: 3 } },
            f: { i: { d: { e: { n: { t: { ".": 45 } } } } } },
            t: {
              i: {
                n: {
                  g: { e: { n: { t: { ".": 33 } } } },
                  e: { n: { t: { ".": 45 } } }
                }
              }
            },
            n: { i: { v: { e: { n: { t: { ".": 45 } } } } } }
          },
          g: { n: { i: { t: { i: 44 } } } },
          r: { p: { u: { l: { e: { n: { t: { ".": 45 } } } } } } },
          m: { p: { é: { t: { e: { n: { t: { ".": 45 } } } } } } }
        },
        9
      ],
      ô: 9,
      œ: 9,
      r: [{ e: { ".": 25, s: { ".": 25 }, n: { t: { ".": 26 } } } }, 15],
      u: [{ r: { r: { e: { n: { t: { ".": 5 } } } } } }, 9],
      û: 9,
      y: [{ r: { i: { l: { l: 45 } } } }, 9],
      c: { i: { d: { e: { n: { t: { ".": 5 } } } } } }
    },
    j: [
      {
        a: { c: { e: { n: { t: { ".": 4 } } } } },
        k: 26,
        e: { ".": 25, s: { ".": 25 }, n: { t: { ".": 26 } } }
      },
      9
    ],
    é: {
      c: {
        e: { n: { t: { ".": 32 } } },
        i: { m: { e: { n: { t: { ".": 22 } } } } },
        u: { m: { e: { n: { t: { ".": 22 } } } } }
      },
      d: {
        e: { n: { t: { ".": 32 } } },
        h: { i: 3 },
        r: { i: { e: 15, q: { u: { e: 15 } } } }
      },
      l: {
        e: { c: { t: { r: 15 } } },
        é: { m: { e: { n: { t: 15 } } } },
        i: { m: { e: { n: { t: { ".": 22 } } } } },
        o: { q: { u: { e: { n: { t: { ".": 5 } } } } } }
      },
      n: { e: { r: { g: 15 } }, i: { t: { e: { n: { t: { ".": 5 } } } } } },
      p: { i: { s: { c: { o: { p: [{ e: 8 }, 20] } } } } },
      m: { i: { l: { l: 43 } } },
      q: {
        u: {
          i: {
            v: { a: { l: { e: { n: { t: { ".": 58 } } } } } },
            p: { o: { t: { e: { n: { t: { ".": 33 } } } } } }
          },
          e: { n: { t: { ".": 32 } } }
        }
      },
      r: { e: { n: { t: { ".": 32 } } } }
    },
    m: {
      u: [
        { n: { i: { f: { i: { c: { e: { n: { t: { ".": 33 } } } } } } } } },
        9
      ],
      i: [
        {
          l: { l: [{ e: { t: 42 } }, 5] },
          m: { e: { n: { t: { ".": 3 } } } },
          t: { t: { e: { n: { t: { ".": 5 } } } } }
        },
        9
      ],
      o: [
        {
          n: {
            o: { v: { a: { l: { e: { n: { t: { ".": 33 } } } } } } },
            t: { r: { é: { a: { l: 20 } } } }
          },
          y: { e: { n: { â: { g: 63 } } } }
        },
        9
      ],
      a: 9,
      â: 9,
      e: [{ ".": 25, s: { ".": 25 } }, 9],
      é: [{ c: { o: { n: { t: { e: { n: { t: { ".": 45 } } } } } } } }, 9],
      è: 9,
      ê: 9,
      î: 9,
      n: { é: { m: { o: 15 }, s: { i: 15 } }, è: { s: 15 } },
      ô: 9,
      œ: 9,
      s: 6,
      û: 9,
      y: 9
    },
    r: {
      é: [
        {
          t: { i: { c: { e: { n: { t: { ".": 34 } } } } } },
          g: { e: { n: { t: { ".": 4 } } } },
          s: { u: { r: { g: { e: { n: { t: { ".": 45 } } } } } } },
          m: { a: { n: { e: { n: { t: { ".": 34 } } } } } }
        },
        9
      ],
      i: [
        {
          n: { g: { e: { n: { t: { ".": 5 } } } } },
          m: { e: { n: { t: { ".": 3 } } } }
        },
        9
      ],
      c: { i: { l: { l: 43 } } },
      m: { i: { l: { l: 43 } } },
      e: [
        {
          l: {
            e: { n: { t: { ".": 4 } } },
            i: { m: { e: { n: { t: { ".": 18 } } } } }
          },
          p: { e: { n: { t: { ".": 4 } } } },
          ".": 25,
          s: { ".": 25 },
          n: { t: { ".": 26 } }
        },
        9
      ],
      u: [{ l: { e: { n: { t: { ".": 4 } } } } }, 9],
      a: [
        {
          m: { e: { n: { t: { ".": 3 } } } },
          i: { m: { e: { n: { t: { ".": 5 } } } } },
          d: { i: { o: { a: 12 } } }
        },
        9
      ],
      y: [{ t: { h: { m: { e: { n: { t: { ".": 18 } } } } } } }, 9],
      â: 9,
      è: 9,
      ê: 9,
      h: [
        { e: { ".": 25, s: { ".": 25 }, u: { r: 73 } }, y: { d: { r: 73 } } },
        15
      ],
      î: 9,
      o: 9,
      ô: 9,
      û: 9
    },
    p: {
      r: [
        {
          i: {
            v: {
              a: {
                t: {
                  d: {
                    o: {
                      c: { e: { n: { t: { ".": 35 } } } },
                      z: { e: { n: { t: { ".": 35 } } } }
                    }
                  }
                }
              }
            }
          },
          u: { d: { e: { n: { t: { ".": 5 } } } } },
          é: {
            é: { m: { i: { n: { e: { n: { t: { ".": 33 } } } } } } },
            s: { e: { n: { t: { ".": 5 } } } }
          },
          o: {
            é: { m: { i: { n: { e: { n: { t: { ".": 33 } } } } } } },
            s: { t: { a: { t: 20 } } }
          },
          e: { ".": 25, s: { ".": 25 }, n: { t: { ".": 26 } } }
        },
        15
      ],
      u: [
        {
          g: { n: { a: { b: { l: { e: 44 } }, c: 44 } } },
          p: { i: { l: { l: 45 } } },
          s: { i: { l: { l: 45 } } }
        },
        9
      ],
      a: [
        {
          p: { i: { l: { l: { a: 45, e: 45, i: 45, o: { m: 45 } } } } },
          l: { é: { o: { é: 12 } } }
        },
        9
      ],
      i: [{ r: { i: { l: { l: 45 } } } }, 9],
      o: [
        {
          l: {
            y: {
              v: { a: { l: { e: { n: { t: { ".": 33 } } } } } },
              a: 17,
              e: 17,
              é: 17,
              è: 17,
              i: 17,
              o: 17,
              s: 17,
              u: 17
            }
          },
          a: { s: { t: { r: { e: 28 } } } }
        },
        9
      ],
      l: [
        {
          u: { m: { e: { n: { t: { ".": 22 } } } } },
          e: { ".": 25, s: { ".": 25 }, n: { t: { ".": 26 } } }
        },
        15
      ],
      e: [
        {
          r: {
            m: { a: { n: { e: { n: { t: { ".": 45 } } } } } },
            t: { i: { n: { e: { n: { t: { ".": 45 } } } } } },
            h: 5
          },
          ".": 25,
          s: { ".": 25 },
          n: { t: { ".": 26 } }
        },
        9
      ],
      â: 9,
      é: [{ n: { u: { l: 3 } }, r: { é: { q: 67 } } }, 9],
      è: 9,
      ê: 9,
      h: [
        {
          ".": 25,
          e: { ".": 25, s: { ".": 25 }, n: { t: { ".": 26 } } },
          l: [{ e: { ".": 25, s: { ".": 25 } } }, 3],
          n: 26,
          o: { t: { o: { s: 12 } } },
          r: [{ e: { ".": 25, s: { ".": 25 } } }, 3],
          s: 26,
          t: [{ a: { l: { é: 69 } }, i: { s: 69 } }, 26]
        },
        15
      ],
      î: 9,
      n: { é: 15, e: { u: 15 } },
      ô: 9,
      s: { y: { c: { h: 15 } } },
      t: { è: { r: 15 }, é: { r: 15 } },
      û: 9,
      y: 9
    },
    i: {
      n: {
        n: { o: { c: { e: { n: { t: { ".": 34 } } } } } },
        c: { i: { d: { e: { n: { t: { ".": 34 } } } } } },
        d: {
          i: { g: { e: { n: { t: { ".": 34 } } } } },
          u: { l: { g: { e: { n: { t: { ".": 45 } } } } } },
          o: { l: { e: { n: { t: { ".": 34 } } } } }
        },
        t: {
          e: { l: { l: { i: { g: { e: { n: { t: { ".": 52 } } } } } } } },
          i: { m: { e: { n: { t: { ".": 18 } } } } }
        },
        s: {
          t: { i: { l: { l: 33 } } },
          o: { l: { e: { n: { t: { ".": 34 } } } } }
        },
        f: { o: { r: { m: { a: { t: 9 } } } } }
      },
      s: {
        c: { e: { n: { t: { ".": 4 } } }, h: { é: 23, i: { a: 23, o: 23 } } },
        t: { a: { t: 6 } }
      },
      m: {
        m: {
          i: {
            s: { c: { e: { n: { t: { ".": 37 } } } } },
            n: { e: { n: { t: { ".": 34 } } } }
          },
          a: { n: { e: { n: { t: { ".": 34 } } } } }
        },
        p: {
          u: { d: { e: { n: { t: { ".": 34 } } } } },
          o: { t: { e: { n: { t: { ".": 34 } } } } }
        }
      },
      a: { l: { g: { i: 56 } }, r: { t: { h: { r: 56 } } } },
      è: { d: { r: { e: 6 } } },
      l: { l: 3 },
      b: { r: { i: { l: { l: 45 } } } },
      o: { a: { c: { t: 27 } }, x: { y: 56 } },
      v: { a: { l: { e: { n: { t: { ".": 5 } } } } } }
    },
    e: {
      s: {
        c: { e: { n: { t: { ".": 4 } } }, o: { p: 23 }, h: 23 },
        t: { i: { m: { e: { n: { t: { ".": 18 } } } } } }
      },
      n: {
        i: { v: { r: 49 } },
        t: { r: { e: { g: { e: { n: { t: { ".": 45 } } } } } } }
      },
      u: { s: { t: { a: { t: 27 } } } },
      x: { t: { r: { a: [{ c: 19, i: 19 }, 51] } } },
      r: { m: { e: { n: { t: { ".": 3 } } } } }
    },
    d: {
      "'": 9,
      a: [{ m: { e: { n: { t: { ".": 3 } } } } }, 9],
      â: 9,
      d: { h: 6 },
      e: [{ ".": 25, s: { ".": 25 }, n: { t: { ".": 26 } } }, 9],
      é: [
        {
          c: { a: { d: { e: { n: { t: { ".": 34 } } } } } },
          t: { r: { i: { m: { e: { n: { t: { ".": 45 } } } } } } }
        },
        9
      ],
      è: 9,
      ê: 9,
      i: [
        {
          s: {
            s: { i: { d: { e: { n: { t: { ".": 45 } } } } } },
            c: { o: { p: 44 } },
            t: { i: { l: { l: 33 } } }
          },
          l: { i: { g: { e: { n: { t: { ".": 34 } } } } } },
          a: {
            p: {
              h: { r: { a: { g: { m: { e: { n: { t: { ".": 62 } } } } } } } }
            }
          }
        },
        9
      ],
      h: { a: { l: 48 }, o: { u: { d: 48 } } },
      î: 9,
      l: { e: { n: { t: { ".": 26 } } } },
      o: 9,
      ô: 9,
      r: [{ e: { ".": 25, s: { ".": 25 }, n: { t: { ".": 26 } } } }, 15],
      s: 6,
      u: 9,
      û: 9,
      y: 9
    },
    t: {
      r: [
        {
          i: { d: { e: { n: { t: { ".": 5 } } } } },
          u: { c: { u: { l: { e: { n: { t: { ".": 45 } } } } } } },
          a: {
            n: {
              s: {
                p: [{ a: { r: { e: { n: { t: { ".": 52 } } } } } }, 21],
                a: [{ c: { t: 71 }, t: { s: 71 } }, 63],
                h: 21,
                o: 63,
                u: 63
              }
            }
          },
          e: { ".": 25, s: { ".": 25 }, n: { t: { ".": 26 } } }
        },
        15
      ],
      a: [
        {
          n: { g: { e: { n: { t: { ".": 5 } } } } },
          m: { e: { n: { t: { ".": 3 } } } },
          c: { h: { y: { a: 12 } } }
        },
        9
      ],
      e: [
        {
          r: { g: { e: { n: { t: { ".": 5 } } } } },
          m: {
            p: { é: { r: { a: { m: { e: { n: { t: { ".": 52 } } } } } } } }
          },
          s: { t: { a: { m: { e: { n: { t: { ".": 45 } } } } } }, ".": 25 },
          ".": 25,
          n: { t: { ".": 26 } }
        },
        9
      ],
      h: [
        {
          r: [{ i: { l: { l: 45 } }, e: { ".": 25, s: { ".": 25 } } }, 3],
          ".": 25,
          e: {
            ".": 25,
            s: { ".": 25 },
            r: { m: { o: { s: 13 } } },
            u: { r: 73 }
          },
          l: 26,
          m: 26,
          n: 26,
          s: 26
        },
        15
      ],
      u: [
        {
          r: { b: { u: { l: { e: { n: { t: { ".": 45 } } } } } } },
          m: { e: { n: { t: { ".": 3 } } } },
          n: { g: { s: 21 } }
        },
        9
      ],
      o: [
        {
          m: { e: { n: { t: { ".": 3 } } } },
          r: { r: { e: { n: { t: { ".": 5 } } } } }
        },
        9
      ],
      â: 9,
      à: 9,
      c: { h: { i: { n: { t: 74 } } } },
      é: [{ l: { é: { e: 17, i: 17, o: { b: 17, p: 17 }, s: 17 } } }, 9],
      è: 9,
      ê: 9,
      i: 9,
      î: 9,
      ô: 9,
      t: { l: 6 },
      û: 9,
      y: 9
    },
    f: {
      a: [{ m: { e: { n: { t: { ".": 3 } } } } }, 9],
      â: 9,
      e: [{ ".": 25, s: { ".": 25 }, n: { t: { ".": 26 } } }, 9],
      é: [{ c: { u: { l: { e: { n: { t: { ".": 34 } } } } } } }, 9],
      è: 9,
      ê: 9,
      i: [
        {
          r: { m: { e: { n: { t: { ".": 22 } } } } },
          c: { h: { u: { m: { e: { n: { t: { ".": 45 } } } } } } }
        },
        9
      ],
      î: 9,
      l: [
        {
          e: { ".": 25, s: { ".": 25 }, n: { t: { ".": 26 } } },
          a: { m: { m: { e: { n: { t: { ".": 18 } } } } } }
        },
        15
      ],
      o: 9,
      ô: 9,
      r: [
        {
          e: { ".": 25, s: { ".": 25 }, n: { t: { ".": 26 } } },
          i: { t: { i: { l: { l: 33 } } } }
        },
        15
      ],
      s: 6,
      u: [{ m: { e: { n: { t: { ".": 3 } } } } }, 9],
      û: 9,
      y: 9
    },
    g: {
      a: 9,
      â: 9,
      e: [{ ".": 25, s: { ".": 25 }, n: { t: { ".": 26 } } }, 9],
      é: 9,
      è: 9,
      ê: 9,
      h: { a: 15, e: 15, i: 15, o: 15, y: 15 },
      i: [{ l: { l: 5 } }, 9],
      î: 9,
      l: [{ e: { ".": 25, s: { ".": 25 }, n: { t: { ".": 26 } } } }, 15],
      n: [{ e: { ".": 25, s: { ".": 25 }, n: { t: { ".": 26 } } } }, 15],
      o: 9,
      ô: 9,
      r: [
        {
          e: { ".": 25, s: { ".": 25 }, n: { t: { ".": 26 } } },
          a: {
            m: { m: { e: { n: { t: { ".": 18 } } } } },
            n: {
              d: {
                i: { l: { o: { q: { u: { e: { n: { t: { ".": 35 } } } } } } } }
              }
            }
          }
        },
        15
      ],
      u: [{ e: { ".": 25, s: { ".": 25 }, n: { t: { ".": 26 } } } }, 9],
      û: 9,
      s: 6,
      y: 9
    },
    s: {
      e: [
        {
          r: {
            g: { e: { n: { t: { ".": 5 } } } },
            p: { e: { n: { t: { ".": 5 } } } }
          },
          m: { i: { l: { l: 37 } } },
          s: { q: { u: { i: { a: 13 } } }, ".": 25 },
          ".": 25,
          n: { t: { ".": 26 } }
        },
        9
      ],
      u: [
        {
          c: { c: { u: { l: { e: { n: { t: { ".": 45 } } } } } } },
          b: { l: { i: { m: { e: { n: { t: { ".": 19 } } } } } }, s: 29 },
          m: { e: { n: { t: { ".": 3 } } } },
          r: {
            é: { m: { i: { n: { e: { n: { t: { ".": 33 } } } } } } },
            a: { h: 47 }
          },
          p: { e: { r: [{ o: 54, s: 54 }, 55] } }
        },
        9
      ],
      p: {
        o: { r: [{ u: { l: { e: { n: { t: { ".": 37 } } } } } }, 15] },
        a: { t: { i: { a: 15 } } },
        e: { r: { m: 15 } },
        h: { è: { r: 15 }, é: { r: 15 } },
        i: { e: { l: 15 }, r: { o: { s: 15 } } }
      },
      l: {
        a: { l: { o: { m: { e: { n: { t: { ".": 19 } } } } } }, v: 15 },
        o: { v: 15 }
      },
      a: 9,
      â: 9,
      c: {
        a: { p: { h: 15 } },
        l: { é: { r: 15 } },
        o: { p: 15 },
        h: [{ ".": 25, e: { ".": 25, s: { ".": 25 } }, s: 26 }, 15]
      },
      é: 9,
      è: 9,
      ê: 9,
      h: [
        {
          ".": 25,
          e: { ".": 25, s: { ".": 25 }, n: { t: { ".": 26 } } },
          m: 26,
          o: { m: 73 },
          r: 26,
          s: 26
        },
        15
      ],
      i: 9,
      î: 9,
      o: 9,
      ô: 9,
      œ: 9,
      t: {
        a: { n: { d: { a: { r: { d: 15 } } } } },
        e: { i: { n: 15 } },
        é: { r: { é: { o: { s: 13 } } } },
        i: { g: { m: 15 } },
        o: { c: { k: 15 }, m: { o: { s: 15 } } },
        r: { o: { p: { h: 15 } }, u: { c: { t: { u: 15 } } } },
        y: { l: { e: 15 } }
      },
      û: 9,
      y: 9
    },
    o: {
      g: { n: { o: { m: { o: { n: { i: 23 } } }, s: { i: 23 } } } },
      p: { u: { l: { e: { n: { t: { ".": 5 } } } } } },
      m: {
        m: { e: { n: { t: { ".": 3 } } } },
        b: { u: { d: { s: 65 } } },
        n: { i: { s: 17, p: { o: { t: { e: { n: { t: { ".": 33 } } } } } } } }
      },
      r: { m: { e: { n: { t: { ".": 3 } } } } },
      b: { l: { o: { n: { g: 23 } } } },
      c: { t: { e: { t: 9 } } },
      d: { l: 6 },
      è: { d: { r: { e: 6 } } },
      i: { o: { n: { i: 56 } } },
      s: {
        t: {
          a: { s: 6, t: 6 },
          é: { r: { o: 6 } },
          i: { m: 6 },
          o: { m: 6 },
          r: {
            a: { d: 6, t: { u: 6 } },
            i: { c: { t: { i: { o: { n: 6 } } } } }
          }
        }
      },
      x: { y: { a: 29 } }
    },
    w: {
      a: [{ g: { n: 44 } }, 9],
      e: [{ ".": 25, s: { ".": 25 }, n: { t: { ".": 26 } } }, 9],
      i: 9,
      o: 9,
      u: 9,
      r: 15
    },
    h: {
      a: 9,
      â: 9,
      e: [{ ".": 25, s: { ".": 25 } }, 9],
      é: [{ m: { i: { é: 53 }, o: { p: { t: 17 } } } }, 9],
      è: 9,
      ê: 9,
      i: [{ l: { l: 5 } }, 9],
      î: 9,
      o: 9,
      ô: 9,
      u: [{ m: { e: { n: { t: { ".": 3 } } } } }, 9],
      û: 9,
      y: [
        {
          p: {
            e: { r: [{ a: 54, e: 54, é: 54, i: 54, o: 54, s: 54, u: 54 }, 55] },
            o: { a: 17, e: 17, é: 17, i: 17, o: 17, s: 17, u: 17 }
          }
        },
        9
      ]
    },
    u: {
      c: { i: { l: { l: 43 } } },
      e: { v: { i: { l: { l: 37 } } } },
      v: { i: { l: { l: 43 } } },
      n: { i: { o: { v: 29 }, a: { x: 29 } } },
      s: { t: { r: 23 } }
    },
    v: {
      a: [
        {
          c: { i: { l: { l: 37 } } },
          n: { i: { l: { l: { i: { n: 45, s: 45 } } } } }
        },
        9
      ],
      i: [
        { l: { l: 5 }, d: { i: { m: { e: { n: { t: { ".": 18 } } } } } } },
        9
      ],
      e: [
        {
          n: {
            i: { m: { e: { n: { t: { ".": 18 } } } } },
            t: {
              r: { i: { p: { o: { t: { e: { n: { t: { ".": 35 } } } } } } } },
              ".": 26
            }
          },
          ".": 25,
          s: { ".": 25 }
        },
        9
      ],
      â: 9,
      é: [{ l: { o: { s: { k: { i: 17 } } } } }, 9],
      è: 9,
      ê: 9,
      î: 9,
      o: [{ l: { t: { a: { m: { p: 70 } } } } }, 9],
      ô: 9,
      r: [{ e: { ".": 25, s: { ".": 25 }, n: { t: { ".": 26 } } } }, 15],
      u: 9,
      û: 9,
      y: 9
    },
    l: {
      i: [{ l: { l: 5 } }, 9],
      l: { i: { o: { n: 32 } }, u: { m: { e: { n: { t: { ".": 22 } } } } } },
      a: [{ w: { r: { e: 44 } } }, 9],
      â: 9,
      à: 9,
      e: [{ ".": 25, s: { ".": 25 }, n: { t: { ".": 26 } } }, 9],
      é: 9,
      è: 9,
      ê: 9,
      î: 9,
      o: 9,
      ô: 9,
      s: { t: 6 },
      u: 9,
      û: 9,
      y: 9,
      m: { e: { n: { t: { ".": 10 } } } }
    },
    x: { i: { l: { l: 5 } }, e: { n: { t: { ".": 26 } } } },
    k: {
      a: 9,
      â: 9,
      e: [{ ".": 25, s: { ".": 25 }, n: { t: { ".": 26 } } }, 9],
      é: 9,
      è: 9,
      ê: 9,
      h: [{ ".": 25 }, 15],
      i: 9,
      î: 9,
      o: 9,
      ô: 9,
      r: 15,
      u: 9,
      û: 9,
      y: 9
    },
    â: { m: { e: { n: { t: { ".": 10 } } } } },
    q: [
      {
        u: {
          a: { m: { e: { n: { t: { ".": 22 } } } } },
          e: { ".": 25, s: { ".": 25 }, n: { t: { ".": 26 } } }
        }
      },
      9
    ],
    è: { m: { e: { n: { t: { ".": 10 } } } } },
    n: {
      u: [{ t: { r: { i: { m: { e: { n: { t: { ".": 45 } } } } } } } }, 9],
      a: 9,
      â: 9,
      e: [{ ".": 25, s: { ".": 25 }, n: { t: { ".": 26 } } }, 9],
      é: 9,
      è: 9,
      ê: 9,
      i: 9,
      î: 9,
      o: 9,
      ô: 9,
      œ: 9,
      û: 9,
      s: { a: { t: { ".": 64, s: { ".": 64 } } } },
      x: 56,
      y: 9
    },
    ô: { m: { e: { n: { t: { ".": 10 } } } } },
    y: {
      a: { s: { t: { h: 56 } }, l: { g: { i: 56 } } },
      s: { t: { o: { m: 6 } } }
    },
    z: {
      a: 9,
      e: [{ ".": 25, s: { ".": 25 }, n: { t: { ".": 26 } } }, 9],
      é: 9,
      è: 9,
      i: 9,
      o: 9,
      u: 9,
      y: 9
    }
  },
  {}
]);

// Césure française du texte justifié (refonte du 23 octobre 2026, demande de Lucas). Le navigateur ne coupe pas les
// mots français sous Windows, si bien qu'un texte justifié laisse de grands blancs entre les mots. Les règles de césure
// de TeX (module hyphen, licence ISC, texte joint) placent des césures possibles invisibles, dont on écarte les coupures
// ridicules : mots de moins de sept lettres, moins de trois lettres d'un côté de la coupure, noms propres, sigles,
// nombres. Seul le texte justifié est traité ; tableaux, titres, légendes et boutons ne le sont jamais.
(function(){
  if(!window.createHyphenator||!window.hyphenationPatternsFr)return;
  var SH="­",couperBrut=createHyphenator(hyphenationPatternsFr,{hyphenChar:SH,minWordLength:7});
  var MOT=/[A-Za-zÀ-ÖØ-öø-ÿŒœÆæ]+(?:['’][A-Za-zÀ-ÖØ-öø-ÿŒœÆæ]+)?/g,MAJ=/^[A-ZÀ-ÖØ-ÞŒÆ]/;
  var EXCLUS="table,nav.site,code,pre,svg,figcaption,button,select,h1,h2,h3,h4,h5,h6,.legende,.tip,#bulle,.sommaire";
  function couper(w){
    if(w.length<7||MAJ.test(w))return w;
    var parts=couperBrut(w).split(SH);if(parts.length<2)return w;
    var out=parts[0],avant=parts[0].length;
    for(var i=1;i<parts.length;i++){if(avant>=3&&w.length-avant>=3)out+=SH;out+=parts[i];avant+=parts[i].length}
    return out}
  function traiter(racine){
    if(!racine)return;
    var parents=new Map(),tw=document.createTreeWalker(racine,NodeFilter.SHOW_TEXT),n,noeuds=[];
    while((n=tw.nextNode())){var p=n.parentElement;if(!p||n.nodeValue.length<7||n.nodeValue.indexOf(SH)>=0)continue;
      var ok=parents.get(p);if(ok===undefined){ok=!p.closest(EXCLUS)&&getComputedStyle(p).textAlign==="justify";parents.set(p,ok)}
      if(ok)noeuds.push(n)}
    noeuds.forEach(function(t){var v=t.nodeValue.replace(MOT,couper);if(v!==t.nodeValue)t.nodeValue=v})}
  window.cesure=traiter;
  function lancer(){traiter(document.querySelector("main")||document.body)}
  // les césures invisibles ne partent ni dans un copier-coller ni dans une impression (le PDF les garderait dans son
  // texte, qui se copierait abîmé, audit externe du 30 octobre 2026) ; elles reviennent après l'impression
  function retirer(){var tw=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT),n;
    while((n=tw.nextNode()))if(n.nodeValue.indexOf(SH)>=0)n.nodeValue=n.nodeValue.split(SH).join("")}
  document.addEventListener("copy",function(e){var s=window.getSelection(),t=s?String(s):"";
    if(t.indexOf(SH)<0||!e.clipboardData)return;e.clipboardData.setData("text/plain",t.split(SH).join(""));e.preventDefault()});
  window.addEventListener("beforeprint",retirer);
  window.addEventListener("afterprint",lancer);
  if("requestIdleCallback" in window)requestIdleCallback(lancer,{timeout:1200});else setTimeout(lancer,150);
})();
