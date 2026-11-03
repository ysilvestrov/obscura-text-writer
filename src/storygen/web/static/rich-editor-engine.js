var __defProp = Object.defineProperty;
var __export = (target, all2) => {
  for (var name in all2)
    __defProp(target, name, { get: all2[name], enumerable: true });
};

// node_modules/.pnpm/orderedmap@2.1.1/node_modules/orderedmap/dist/index.js
function OrderedMap(content3) {
  this.content = content3;
}
OrderedMap.prototype = {
  constructor: OrderedMap,
  find: function(key2) {
    for (var i2 = 0; i2 < this.content.length; i2 += 2)
      if (this.content[i2] === key2) return i2;
    return -1;
  },
  // :: (string) → ?any
  // Retrieve the value stored under `key`, or return undefined when
  // no such key exists.
  get: function(key2) {
    var found2 = this.find(key2);
    return found2 == -1 ? void 0 : this.content[found2 + 1];
  },
  // :: (string, any, ?string) → OrderedMap
  // Create a new map by replacing the value of `key` with a new
  // value, or adding a binding to the end of the map. If `newKey` is
  // given, the key of the binding will be replaced with that key.
  update: function(key2, value, newKey) {
    var self = newKey && newKey != key2 ? this.remove(newKey) : this;
    var found2 = self.find(key2), content3 = self.content.slice();
    if (found2 == -1) {
      content3.push(newKey || key2, value);
    } else {
      content3[found2 + 1] = value;
      if (newKey) content3[found2] = newKey;
    }
    return new OrderedMap(content3);
  },
  // :: (string) → OrderedMap
  // Return a map with the given key removed, if it existed.
  remove: function(key2) {
    var found2 = this.find(key2);
    if (found2 == -1) return this;
    var content3 = this.content.slice();
    content3.splice(found2, 2);
    return new OrderedMap(content3);
  },
  // :: (string, any) → OrderedMap
  // Add a new key to the start of the map.
  addToStart: function(key2, value) {
    return new OrderedMap([key2, value].concat(this.remove(key2).content));
  },
  // :: (string, any) → OrderedMap
  // Add a new key to the end of the map.
  addToEnd: function(key2, value) {
    var content3 = this.remove(key2).content.slice();
    content3.push(key2, value);
    return new OrderedMap(content3);
  },
  // :: (string, string, any) → OrderedMap
  // Add a key after the given key. If `place` is not found, the new
  // key is added to the end.
  addBefore: function(place, key2, value) {
    var without = this.remove(key2), content3 = without.content.slice();
    var found2 = without.find(place);
    content3.splice(found2 == -1 ? content3.length : found2, 0, key2, value);
    return new OrderedMap(content3);
  },
  // :: ((key: string, value: any))
  // Call the given function for each key/value pair in the map, in
  // order.
  forEach: function(f) {
    for (var i2 = 0; i2 < this.content.length; i2 += 2)
      f(this.content[i2], this.content[i2 + 1]);
  },
  // :: (union<Object, OrderedMap>) → OrderedMap
  // Create a new map by prepending the keys in this map that don't
  // appear in `map` before the keys in `map`.
  prepend: function(map5) {
    map5 = OrderedMap.from(map5);
    if (!map5.size) return this;
    return new OrderedMap(map5.content.concat(this.subtract(map5).content));
  },
  // :: (union<Object, OrderedMap>) → OrderedMap
  // Create a new map by appending the keys in this map that don't
  // appear in `map` after the keys in `map`.
  append: function(map5) {
    map5 = OrderedMap.from(map5);
    if (!map5.size) return this;
    return new OrderedMap(this.subtract(map5).content.concat(map5.content));
  },
  // :: (union<Object, OrderedMap>) → OrderedMap
  // Create a map containing all the keys in this map that don't
  // appear in `map`.
  subtract: function(map5) {
    var result = this;
    map5 = OrderedMap.from(map5);
    for (var i2 = 0; i2 < map5.content.length; i2 += 2)
      result = result.remove(map5.content[i2]);
    return result;
  },
  // :: () → Object
  // Turn ordered map into a plain object.
  toObject: function() {
    var result = {};
    this.forEach(function(key2, value) {
      result[key2] = value;
    });
    return result;
  },
  // :: number
  // The amount of keys in this map.
  get size() {
    return this.content.length >> 1;
  }
};
OrderedMap.from = function(value) {
  if (value instanceof OrderedMap) return value;
  var content3 = [];
  if (value) for (var prop in value) content3.push(prop, value[prop]);
  return new OrderedMap(content3);
};
var dist_default = OrderedMap;

// node_modules/.pnpm/prosemirror-model@1.25.12/node_modules/prosemirror-model/dist/index.js
function findDiffStart(a, b, pos) {
  for (let i2 = 0; ; i2++) {
    if (i2 == a.childCount || i2 == b.childCount)
      return a.childCount == b.childCount ? null : pos;
    let childA = a.child(i2), childB = b.child(i2);
    if (childA == childB) {
      pos += childA.nodeSize;
      continue;
    }
    if (!childA.sameMarkup(childB))
      return pos;
    if (childA.isText && childA.text != childB.text) {
      let tA = childA.text, tB = childB.text, j = 0;
      for (; tA[j] == tB[j]; j++)
        pos++;
      if (j && j < tA.length && j < tB.length && surrogateHigh(tA.charCodeAt(j - 1)) && surrogateLow(tA.charCodeAt(j)))
        pos--;
      return pos;
    }
    if (childA.content.size || childB.content.size) {
      let inner = findDiffStart(childA.content, childB.content, pos + 1);
      if (inner != null)
        return inner;
    }
    pos += childA.nodeSize;
  }
}
function findDiffEnd(a, b, posA, posB) {
  for (let iA = a.childCount, iB = b.childCount; ; ) {
    if (iA == 0 || iB == 0)
      return iA == iB ? null : { a: posA, b: posB };
    let childA = a.child(--iA), childB = b.child(--iB), size = childA.nodeSize;
    if (childA == childB) {
      posA -= size;
      posB -= size;
      continue;
    }
    if (!childA.sameMarkup(childB))
      return { a: posA, b: posB };
    if (childA.isText && childA.text != childB.text) {
      let tA = childA.text, tB = childB.text, iA2 = tA.length, iB2 = tB.length;
      while (iA2 > 0 && iB2 > 0 && tA[iA2 - 1] == tB[iB2 - 1]) {
        iA2--;
        iB2--;
        posA--;
        posB--;
      }
      if (iA2 && iB2 && iA2 < tA.length && surrogateHigh(tA.charCodeAt(iA2 - 1)) && surrogateLow(tA.charCodeAt(iA2))) {
        posA++;
        posB++;
      }
      return { a: posA, b: posB };
    }
    if (childA.content.size || childB.content.size) {
      let inner = findDiffEnd(childA.content, childB.content, posA - 1, posB - 1);
      if (inner)
        return inner;
    }
    posA -= size;
    posB -= size;
  }
}
function surrogateLow(ch) {
  return ch >= 56320 && ch < 57344;
}
function surrogateHigh(ch) {
  return ch >= 55296 && ch < 56320;
}
var Fragment = class _Fragment {
  /**
  @internal
  */
  constructor(content3, size) {
    this.content = content3;
    this.size = size || 0;
    if (size == null)
      for (let i2 = 0; i2 < content3.length; i2++)
        this.size += content3[i2].nodeSize;
  }
  /**
  Invoke a callback for all descendant nodes between the given two
  positions (relative to start of this fragment). Doesn't descend
  into a node when the callback returns `false`.
  */
  nodesBetween(from2, to, f, nodeStart = 0, parent) {
    for (let i2 = 0, pos = 0; pos < to; i2++) {
      let child = this.content[i2], end = pos + child.nodeSize;
      if (end > from2 && f(child, nodeStart + pos, parent || null, i2) !== false && child.content.size) {
        let start = pos + 1;
        child.nodesBetween(Math.max(0, from2 - start), Math.min(child.content.size, to - start), f, nodeStart + start);
      }
      pos = end;
    }
  }
  /**
  Call the given callback for every descendant node. `pos` will be
  relative to the start of the fragment. The callback may return
  `false` to prevent traversal of a given node's children.
  */
  descendants(f) {
    this.nodesBetween(0, this.size, f);
  }
  /**
  Extract the text between `from` and `to`. See the same method on
  [`Node`](https://prosemirror.net/docs/ref/#model.Node.textBetween).
  */
  textBetween(from2, to, blockSeparator, leafText) {
    let text4 = "", first = true;
    this.nodesBetween(from2, to, (node2, pos) => {
      let nodeText = node2.isText ? node2.text.slice(Math.max(from2, pos) - pos, to - pos) : !node2.isLeaf ? "" : leafText ? typeof leafText === "function" ? leafText(node2) : leafText : node2.type.spec.leafText ? node2.type.spec.leafText(node2) : "";
      if (node2.isBlock && (node2.isLeaf && nodeText || node2.isTextblock) && blockSeparator) {
        if (first)
          first = false;
        else
          text4 += blockSeparator;
      }
      text4 += nodeText;
    }, 0);
    return text4;
  }
  /**
  Create a new fragment containing the combined content of this
  fragment and the other.
  */
  append(other) {
    if (!other.size)
      return this;
    if (!this.size)
      return other;
    let last = this.lastChild, first = other.firstChild, content3 = this.content.slice(), i2 = 0;
    if (last.isText && last.sameMarkup(first)) {
      content3[content3.length - 1] = last.withText(last.text + first.text);
      i2 = 1;
    }
    for (; i2 < other.content.length; i2++)
      content3.push(other.content[i2]);
    return new _Fragment(content3, this.size + other.size);
  }
  /**
  Cut out the sub-fragment between the two given positions.
  */
  cut(from2, to = this.size) {
    if (from2 == 0 && to == this.size)
      return this;
    let result = [], size = 0;
    if (to > from2)
      for (let i2 = 0, pos = 0; pos < to; i2++) {
        let child = this.content[i2], end = pos + child.nodeSize;
        if (end > from2) {
          if (pos < from2 || end > to) {
            if (child.isText)
              child = child.cut(Math.max(0, from2 - pos), Math.min(child.text.length, to - pos));
            else
              child = child.cut(Math.max(0, from2 - pos - 1), Math.min(child.content.size, to - pos - 1));
          }
          result.push(child);
          size += child.nodeSize;
        }
        pos = end;
      }
    return new _Fragment(result, size);
  }
  /**
  @internal
  */
  cutByIndex(from2, to) {
    if (from2 == to)
      return _Fragment.empty;
    if (from2 == 0 && to == this.content.length)
      return this;
    return new _Fragment(this.content.slice(from2, to));
  }
  /**
  Create a new fragment in which the node at the given index is
  replaced by the given node.
  */
  replaceChild(index2, node2) {
    let current = this.content[index2];
    if (current == node2)
      return this;
    let copy2 = this.content.slice();
    let size = this.size + node2.nodeSize - current.nodeSize;
    copy2[index2] = node2;
    return new _Fragment(copy2, size);
  }
  /**
  Create a new fragment by prepending the given node to this
  fragment.
  */
  addToStart(node2) {
    return new _Fragment([node2].concat(this.content), this.size + node2.nodeSize);
  }
  /**
  Create a new fragment by appending the given node to this
  fragment.
  */
  addToEnd(node2) {
    return new _Fragment(this.content.concat(node2), this.size + node2.nodeSize);
  }
  /**
  Compare this fragment to another one.
  */
  eq(other) {
    if (this.content.length != other.content.length)
      return false;
    for (let i2 = 0; i2 < this.content.length; i2++)
      if (!this.content[i2].eq(other.content[i2]))
        return false;
    return true;
  }
  /**
  The first child of the fragment, or `null` if it is empty.
  */
  get firstChild() {
    return this.content.length ? this.content[0] : null;
  }
  /**
  The last child of the fragment, or `null` if it is empty.
  */
  get lastChild() {
    return this.content.length ? this.content[this.content.length - 1] : null;
  }
  /**
  The number of child nodes in this fragment.
  */
  get childCount() {
    return this.content.length;
  }
  /**
  Get the child node at the given index. Raise an error when the
  index is out of range.
  */
  child(index2) {
    let found2 = this.content[index2];
    if (!found2)
      throw new RangeError("Index " + index2 + " out of range for " + this);
    return found2;
  }
  /**
  Get the child node at the given index, if it exists.
  */
  maybeChild(index2) {
    return this.content[index2] || null;
  }
  /**
  Call `f` for every child node, passing the node, its offset
  into this parent node, and its index.
  */
  forEach(f) {
    for (let i2 = 0, p = 0; i2 < this.content.length; i2++) {
      let child = this.content[i2];
      f(child, p, i2);
      p += child.nodeSize;
    }
  }
  /**
  Find the first position at which this fragment and another
  fragment differ, or `null` if they are the same.
  */
  findDiffStart(other, pos = 0) {
    return findDiffStart(this, other, pos);
  }
  /**
  Find the first position, searching from the end, at which this
  fragment and the given fragment differ, or `null` if they are
  the same. Since this position will not be the same in both
  nodes, an object with two separate positions is returned.
  */
  findDiffEnd(other, pos = this.size, otherPos = other.size) {
    return findDiffEnd(this, other, pos, otherPos);
  }
  /**
  Find the index and inner offset corresponding to a given relative
  position in this fragment. The result object will be reused
  (overwritten) the next time the function is called. @internal
  */
  findIndex(pos) {
    if (pos == 0)
      return retIndex(0, pos);
    if (pos == this.size)
      return retIndex(this.content.length, pos);
    if (pos > this.size || pos < 0)
      throw new RangeError(`Position ${pos} outside of fragment (${this})`);
    for (let i2 = 0, curPos = 0; ; i2++) {
      let cur = this.child(i2), end = curPos + cur.nodeSize;
      if (end >= pos) {
        if (end == pos)
          return retIndex(i2 + 1, end);
        return retIndex(i2, curPos);
      }
      curPos = end;
    }
  }
  /**
  Return a debugging string that describes this fragment.
  */
  toString() {
    return "<" + this.toStringInner() + ">";
  }
  /**
  @internal
  */
  toStringInner() {
    return this.content.join(", ");
  }
  /**
  Create a JSON-serializeable representation of this fragment.
  */
  toJSON() {
    return this.content.length ? this.content.map((n) => n.toJSON()) : null;
  }
  /**
  Deserialize a fragment from its JSON representation.
  */
  static fromJSON(schema2, value) {
    if (!value)
      return _Fragment.empty;
    if (!Array.isArray(value))
      throw new RangeError("Invalid input for Fragment.fromJSON");
    return _Fragment.fromArray(value.map(schema2.nodeFromJSON));
  }
  /**
  Build a fragment from an array of nodes. Ensures that adjacent
  text nodes with the same marks are joined together.
  */
  static fromArray(array) {
    if (!array.length)
      return _Fragment.empty;
    let joined, size = 0;
    for (let i2 = 0; i2 < array.length; i2++) {
      let node2 = array[i2];
      size += node2.nodeSize;
      if (i2 && node2.isText && array[i2 - 1].sameMarkup(node2)) {
        if (!joined)
          joined = array.slice(0, i2);
        joined[joined.length - 1] = node2.withText(joined[joined.length - 1].text + node2.text);
      } else if (joined) {
        joined.push(node2);
      }
    }
    return new _Fragment(joined || array, size);
  }
  /**
  Create a fragment from something that can be interpreted as a
  set of nodes. For `null`, it returns the empty fragment. For a
  fragment, the fragment itself. For a node or array of nodes, a
  fragment containing those nodes.
  */
  static from(nodes) {
    if (!nodes)
      return _Fragment.empty;
    if (nodes instanceof _Fragment)
      return nodes;
    if (Array.isArray(nodes))
      return this.fromArray(nodes);
    if (nodes.attrs)
      return new _Fragment([nodes], nodes.nodeSize);
    throw new RangeError("Can not convert " + nodes + " to a Fragment" + (nodes.nodesBetween ? " (looks like multiple versions of prosemirror-model were loaded)" : ""));
  }
};
Fragment.empty = new Fragment([], 0);
var found = { index: 0, offset: 0 };
function retIndex(index2, offset) {
  found.index = index2;
  found.offset = offset;
  return found;
}
function compareDeep(a, b) {
  if (a === b)
    return true;
  if (!(a && typeof a == "object") || !(b && typeof b == "object"))
    return false;
  let array = Array.isArray(a);
  if (Array.isArray(b) != array)
    return false;
  if (array) {
    if (a.length != b.length)
      return false;
    for (let i2 = 0; i2 < a.length; i2++)
      if (!compareDeep(a[i2], b[i2]))
        return false;
  } else {
    for (let p in a)
      if (!(p in b) || !compareDeep(a[p], b[p]))
        return false;
    for (let p in b)
      if (!(p in a))
        return false;
  }
  return true;
}
var Mark = class _Mark {
  /**
  @internal
  */
  constructor(type, attrs) {
    this.type = type;
    this.attrs = attrs;
  }
  /**
  Given a set of marks, create a new set which contains this one as
  well, in the right position. If this mark is already in the set,
  the set itself is returned. If any marks that are set to be
  [exclusive](https://prosemirror.net/docs/ref/#model.MarkSpec.excludes) with this mark are present,
  those are replaced by this one.
  */
  addToSet(set) {
    let copy2, placed = false;
    for (let i2 = 0; i2 < set.length; i2++) {
      let other = set[i2];
      if (this.eq(other))
        return set;
      if (this.type.excludes(other.type)) {
        if (!copy2)
          copy2 = set.slice(0, i2);
      } else if (other.type.excludes(this.type)) {
        return set;
      } else {
        if (!placed && other.type.rank > this.type.rank) {
          if (!copy2)
            copy2 = set.slice(0, i2);
          copy2.push(this);
          placed = true;
        }
        if (copy2)
          copy2.push(other);
      }
    }
    if (!copy2)
      copy2 = set.slice();
    if (!placed)
      copy2.push(this);
    return copy2;
  }
  /**
  Remove this mark from the given set, returning a new set. If this
  mark is not in the set, the set itself is returned.
  */
  removeFromSet(set) {
    for (let i2 = 0; i2 < set.length; i2++)
      if (this.eq(set[i2]))
        return set.slice(0, i2).concat(set.slice(i2 + 1));
    return set;
  }
  /**
  Test whether this mark is in the given set of marks.
  */
  isInSet(set) {
    for (let i2 = 0; i2 < set.length; i2++)
      if (this.eq(set[i2]))
        return true;
    return false;
  }
  /**
  Test whether this mark has the same type and attributes as
  another mark.
  */
  eq(other) {
    return this == other || this.type == other.type && compareDeep(this.attrs, other.attrs);
  }
  /**
  Convert this mark to a JSON-serializeable representation.
  */
  toJSON() {
    let obj = { type: this.type.name };
    for (let _ in this.attrs) {
      obj.attrs = this.attrs;
      break;
    }
    return obj;
  }
  /**
  Deserialize a mark from JSON.
  */
  static fromJSON(schema2, json) {
    if (!json)
      throw new RangeError("Invalid input for Mark.fromJSON");
    let type = schema2.marks[json.type];
    if (!type)
      throw new RangeError(`There is no mark type ${json.type} in this schema`);
    let mark = type.create(json.attrs);
    return mark;
  }
  /**
  Test whether two sets of marks are identical.
  */
  static sameSet(a, b) {
    if (a == b)
      return true;
    if (a.length != b.length)
      return false;
    for (let i2 = 0; i2 < a.length; i2++)
      if (!a[i2].eq(b[i2]))
        return false;
    return true;
  }
  /**
  Create a properly sorted mark set from null, a single mark, or an
  unsorted array of marks.
  */
  static setFrom(marks) {
    if (!marks || Array.isArray(marks) && marks.length == 0)
      return _Mark.none;
    if (marks instanceof _Mark)
      return [marks];
    let copy2 = marks.slice();
    copy2.sort((a, b) => a.type.rank - b.type.rank);
    return copy2;
  }
};
Mark.none = [];
var ReplaceError = class extends Error {
};
var Slice = class _Slice {
  /**
  Create a slice. When specifying a non-zero open depth, you must
  make sure that there are nodes of at least that depth at the
  appropriate side of the fragment—i.e. if the fragment is an
  empty paragraph node, `openStart` and `openEnd` can't be greater
  than 1.
  
  It is not necessary for the content of open nodes to conform to
  the schema's content constraints, though it should be a valid
  start/end/middle for such a node, depending on which sides are
  open.
  */
  constructor(content3, openStart, openEnd) {
    this.content = content3;
    this.openStart = openStart;
    this.openEnd = openEnd;
  }
  /**
  The size this slice would add when inserted into a document.
  */
  get size() {
    return this.content.size - this.openStart - this.openEnd;
  }
  /**
  @internal
  */
  insertAt(pos, fragment) {
    let content3 = insertInto(this.content, pos + this.openStart, fragment, this.openStart + 1, this.openEnd + 1);
    return content3 && new _Slice(content3, this.openStart, this.openEnd);
  }
  /**
  @internal
  */
  removeBetween(from2, to) {
    return new _Slice(removeRange(this.content, from2 + this.openStart, to + this.openStart), this.openStart, this.openEnd);
  }
  /**
  Tests whether this slice is equal to another slice.
  */
  eq(other) {
    return this.content.eq(other.content) && this.openStart == other.openStart && this.openEnd == other.openEnd;
  }
  /**
  @internal
  */
  toString() {
    return this.content + "(" + this.openStart + "," + this.openEnd + ")";
  }
  /**
  Convert a slice to a JSON-serializable representation.
  */
  toJSON() {
    if (!this.content.size)
      return null;
    let json = { content: this.content.toJSON() };
    if (this.openStart > 0)
      json.openStart = this.openStart;
    if (this.openEnd > 0)
      json.openEnd = this.openEnd;
    return json;
  }
  /**
  Deserialize a slice from its JSON representation.
  */
  static fromJSON(schema2, json) {
    if (!json)
      return _Slice.empty;
    let openStart = json.openStart || 0, openEnd = json.openEnd || 0;
    if (typeof openStart != "number" || typeof openEnd != "number")
      throw new RangeError("Invalid input for Slice.fromJSON");
    return new _Slice(Fragment.fromJSON(schema2, json.content), openStart, openEnd);
  }
  /**
  Create a slice from a fragment by taking the maximum possible
  open value on both side of the fragment.
  */
  static maxOpen(fragment, openIsolating = true) {
    let openStart = 0, openEnd = 0;
    for (let n = fragment.firstChild; n && !n.isLeaf && (openIsolating || !n.type.spec.isolating); n = n.firstChild)
      openStart++;
    for (let n = fragment.lastChild; n && !n.isLeaf && (openIsolating || !n.type.spec.isolating); n = n.lastChild)
      openEnd++;
    return new _Slice(fragment, openStart, openEnd);
  }
};
Slice.empty = new Slice(Fragment.empty, 0, 0);
function removeRange(content3, from2, to) {
  let { index: index2, offset } = content3.findIndex(from2), child = content3.maybeChild(index2);
  let { index: indexTo, offset: offsetTo } = content3.findIndex(to);
  if (offset == from2 || child.isText) {
    if (offsetTo != to && !content3.child(indexTo).isText)
      throw new RangeError("Removing non-flat range");
    return content3.cut(0, from2).append(content3.cut(to));
  }
  if (index2 != indexTo)
    throw new RangeError("Removing non-flat range");
  return content3.replaceChild(index2, child.copy(removeRange(child.content, from2 - offset - 1, to - offset - 1)));
}
function insertInto(content3, dist, insert, openStart, openEnd, parent) {
  let { index: index2, offset } = content3.findIndex(dist), child = content3.maybeChild(index2);
  if (offset == dist || child.isText) {
    if (parent && openStart <= 0 && openEnd <= 0 && !parent.canReplace(index2, index2, insert))
      return null;
    return content3.cut(0, dist).append(insert).append(content3.cut(dist));
  }
  let inner = insertInto(child.content, dist - offset - 1, insert, index2 == 0 ? openStart - 1 : 0, index2 == content3.childCount - 1 ? openEnd - 1 : 0, child);
  return inner && content3.replaceChild(index2, child.copy(inner));
}
function replace($from, $to, slice2) {
  if (slice2.openStart > $from.depth)
    throw new ReplaceError("Inserted content deeper than insertion position");
  if ($from.depth - slice2.openStart != $to.depth - slice2.openEnd)
    throw new ReplaceError("Inconsistent open depths");
  return replaceOuter($from, $to, slice2, 0);
}
function replaceOuter($from, $to, slice2, depth) {
  let index2 = $from.index(depth), node2 = $from.node(depth);
  if (index2 == $to.index(depth) && depth < $from.depth - slice2.openStart) {
    let inner = replaceOuter($from, $to, slice2, depth + 1);
    return node2.copy(node2.content.replaceChild(index2, inner));
  } else if (!slice2.content.size) {
    return close(node2, replaceTwoWay($from, $to, depth));
  } else if (!slice2.openStart && !slice2.openEnd && $from.depth == depth && $to.depth == depth) {
    let parent = $from.parent, content3 = parent.content;
    return close(parent, content3.cut(0, $from.parentOffset).append(slice2.content).append(content3.cut($to.parentOffset)));
  } else {
    let { start, end } = prepareSliceForReplace(slice2, $from);
    return close(node2, replaceThreeWay($from, start, end, $to, depth));
  }
}
function checkJoin(main, sub) {
  if (!sub.type.compatibleContent(main.type))
    throw new ReplaceError("Cannot join " + sub.type.name + " onto " + main.type.name);
}
function joinable($before, $after, depth) {
  let node2 = $before.node(depth);
  checkJoin(node2, $after.node(depth));
  return node2;
}
function addNode(child, target) {
  let last = target.length - 1;
  if (last >= 0 && child.isText && child.sameMarkup(target[last]))
    target[last] = child.withText(target[last].text + child.text);
  else
    target.push(child);
}
function addRange($start, $end, depth, target) {
  let node2 = ($end || $start).node(depth);
  let startIndex = 0, endIndex = $end ? $end.index(depth) : node2.childCount;
  if ($start) {
    startIndex = $start.index(depth);
    if ($start.depth > depth) {
      startIndex++;
    } else if ($start.textOffset) {
      addNode($start.nodeAfter, target);
      startIndex++;
    }
  }
  for (let i2 = startIndex; i2 < endIndex; i2++)
    addNode(node2.child(i2), target);
  if ($end && $end.depth == depth && $end.textOffset)
    addNode($end.nodeBefore, target);
}
function close(node2, content3) {
  if (!node2.type.validContent(content3))
    throw new ReplaceError("Invalid content for node " + node2.type.name);
  return node2.copy(content3);
}
function replaceThreeWay($from, $start, $end, $to, depth) {
  let openStart = $from.depth > depth && joinable($from, $start, depth + 1);
  let openEnd = $to.depth > depth && joinable($end, $to, depth + 1);
  let content3 = [];
  addRange(null, $from, depth, content3);
  if (openStart && openEnd && $start.index(depth) == $end.index(depth)) {
    checkJoin(openStart, openEnd);
    addNode(close(openStart, replaceThreeWay($from, $start, $end, $to, depth + 1)), content3);
  } else {
    if (openStart)
      addNode(close(openStart, replaceTwoWay($from, $start, depth + 1)), content3);
    addRange($start, $end, depth, content3);
    if (openEnd)
      addNode(close(openEnd, replaceTwoWay($end, $to, depth + 1)), content3);
  }
  addRange($to, null, depth, content3);
  return new Fragment(content3);
}
function replaceTwoWay($from, $to, depth) {
  let content3 = [];
  addRange(null, $from, depth, content3);
  if ($from.depth > depth) {
    let type = joinable($from, $to, depth + 1);
    addNode(close(type, replaceTwoWay($from, $to, depth + 1)), content3);
  }
  addRange($to, null, depth, content3);
  return new Fragment(content3);
}
function prepareSliceForReplace(slice2, $along) {
  let extra = $along.depth - slice2.openStart, parent = $along.node(extra);
  let node2 = parent.copy(slice2.content);
  for (let i2 = extra - 1; i2 >= 0; i2--)
    node2 = $along.node(i2).copy(Fragment.from(node2));
  return {
    start: node2.resolveNoCache(slice2.openStart + extra),
    end: node2.resolveNoCache(node2.content.size - slice2.openEnd - extra)
  };
}
var ResolvedPos = class _ResolvedPos {
  /**
  @internal
  */
  constructor(pos, path, parentOffset) {
    this.pos = pos;
    this.path = path;
    this.parentOffset = parentOffset;
    this.depth = path.length / 3 - 1;
  }
  /**
  @internal
  */
  resolveDepth(val) {
    if (val == null)
      return this.depth;
    if (val < 0)
      return this.depth + val;
    return val;
  }
  /**
  The parent node that the position points into. Note that even if
  a position points into a text node, that node is not considered
  the parent—text nodes are ‘flat’ in this model, and have no content.
  */
  get parent() {
    return this.node(this.depth);
  }
  /**
  The root node in which the position was resolved.
  */
  get doc() {
    return this.node(0);
  }
  /**
  The ancestor node at the given level. `p.node(p.depth)` is the
  same as `p.parent`.
  */
  node(depth) {
    return this.path[this.resolveDepth(depth) * 3];
  }
  /**
  The index into the ancestor at the given level. If this points
  at the 3rd node in the 2nd paragraph on the top level, for
  example, `p.index(0)` is 1 and `p.index(1)` is 2.
  */
  index(depth) {
    return this.path[this.resolveDepth(depth) * 3 + 1];
  }
  /**
  The index pointing after this position into the ancestor at the
  given level.
  */
  indexAfter(depth) {
    depth = this.resolveDepth(depth);
    return this.index(depth) + (depth == this.depth && !this.textOffset ? 0 : 1);
  }
  /**
  The (absolute) position at the start of the node at the given
  level.
  */
  start(depth) {
    depth = this.resolveDepth(depth);
    return depth == 0 ? 0 : this.path[depth * 3 - 1] + 1;
  }
  /**
  The (absolute) position at the end of the node at the given
  level.
  */
  end(depth) {
    depth = this.resolveDepth(depth);
    return this.start(depth) + this.node(depth).content.size;
  }
  /**
  The (absolute) position directly before the wrapping node at the
  given level, or, when `depth` is `this.depth + 1`, the original
  position.
  */
  before(depth) {
    depth = this.resolveDepth(depth);
    if (!depth)
      throw new RangeError("There is no position before the top-level node");
    return depth == this.depth + 1 ? this.pos : this.path[depth * 3 - 1];
  }
  /**
  The (absolute) position directly after the wrapping node at the
  given level, or the original position when `depth` is `this.depth + 1`.
  */
  after(depth) {
    depth = this.resolveDepth(depth);
    if (!depth)
      throw new RangeError("There is no position after the top-level node");
    return depth == this.depth + 1 ? this.pos : this.path[depth * 3 - 1] + this.path[depth * 3].nodeSize;
  }
  /**
  When this position points into a text node, this returns the
  distance between the position and the start of the text node.
  Will be zero for positions that point between nodes.
  */
  get textOffset() {
    return this.pos - this.path[this.path.length - 1];
  }
  /**
  Get the node directly after the position, if any. If the position
  points into a text node, only the part of that node after the
  position is returned.
  */
  get nodeAfter() {
    let parent = this.parent, index2 = this.index(this.depth);
    if (index2 == parent.childCount)
      return null;
    let dOff = this.pos - this.path[this.path.length - 1], child = parent.child(index2);
    return dOff ? parent.child(index2).cut(dOff) : child;
  }
  /**
  Get the node directly before the position, if any. If the
  position points into a text node, only the part of that node
  before the position is returned.
  */
  get nodeBefore() {
    let index2 = this.index(this.depth);
    let dOff = this.pos - this.path[this.path.length - 1];
    if (dOff)
      return this.parent.child(index2).cut(0, dOff);
    return index2 == 0 ? null : this.parent.child(index2 - 1);
  }
  /**
  Get the position at the given index in the parent node at the
  given depth (which defaults to `this.depth`).
  */
  posAtIndex(index2, depth) {
    depth = this.resolveDepth(depth);
    let node2 = this.path[depth * 3], pos = depth == 0 ? 0 : this.path[depth * 3 - 1] + 1;
    for (let i2 = 0; i2 < index2; i2++)
      pos += node2.child(i2).nodeSize;
    return pos;
  }
  /**
  Get the marks at this position, factoring in the surrounding
  marks' [`inclusive`](https://prosemirror.net/docs/ref/#model.MarkSpec.inclusive) property. If the
  position is at the start of a non-empty node, the marks of the
  node after it (if any) are returned.
  */
  marks() {
    let parent = this.parent, index2 = this.index();
    if (parent.content.size == 0)
      return Mark.none;
    if (this.textOffset)
      return parent.child(index2).marks;
    let main = parent.maybeChild(index2 - 1), other = parent.maybeChild(index2);
    if (!main) {
      let tmp = main;
      main = other;
      other = tmp;
    }
    let marks = main.marks;
    for (var i2 = 0; i2 < marks.length; i2++)
      if (marks[i2].type.spec.inclusive === false && (!other || !marks[i2].isInSet(other.marks)))
        marks = marks[i2--].removeFromSet(marks);
    return marks;
  }
  /**
  Get the marks after the current position, if any, except those
  that are non-inclusive and not present at position `$end`. This
  is mostly useful for getting the set of marks to preserve after a
  deletion. Will return `null` if this position is at the end of
  its parent node or its parent node isn't a textblock (in which
  case no marks should be preserved).
  */
  marksAcross($end) {
    let after = this.parent.maybeChild(this.index());
    if (!after || !after.isInline)
      return null;
    let marks = after.marks, next = $end.parent.maybeChild($end.index());
    for (var i2 = 0; i2 < marks.length; i2++)
      if (marks[i2].type.spec.inclusive === false && (!next || !marks[i2].isInSet(next.marks)))
        marks = marks[i2--].removeFromSet(marks);
    return marks;
  }
  /**
  The depth up to which this position and the given (non-resolved)
  position share the same parent nodes.
  */
  sharedDepth(pos) {
    for (let depth = this.depth; depth > 0; depth--)
      if (this.start(depth) <= pos && this.end(depth) >= pos)
        return depth;
    return 0;
  }
  /**
  Returns a range based on the place where this position and the
  given position diverge around block content. If both point into
  the same textblock, for example, a range around that textblock
  will be returned. If they point into different blocks, the range
  around those blocks in their shared ancestor is returned. You can
  pass in an optional predicate that will be called with a parent
  node to see if a range into that parent is acceptable.
  */
  blockRange(other = this, pred) {
    if (other.pos < this.pos)
      return other.blockRange(this);
    for (let d = this.depth - (this.parent.inlineContent || this.pos == other.pos ? 1 : 0); d >= 0; d--)
      if (other.pos <= this.end(d) && (!pred || pred(this.node(d))))
        return new NodeRange(this, other, d);
    return null;
  }
  /**
  Query whether the given position shares the same parent node.
  */
  sameParent(other) {
    return this.pos - this.parentOffset == other.pos - other.parentOffset;
  }
  /**
  Return the greater of this and the given position.
  */
  max(other) {
    return other.pos > this.pos ? other : this;
  }
  /**
  Return the smaller of this and the given position.
  */
  min(other) {
    return other.pos < this.pos ? other : this;
  }
  /**
  @internal
  */
  toString() {
    let str = "";
    for (let i2 = 1; i2 <= this.depth; i2++)
      str += (str ? "/" : "") + this.node(i2).type.name + "_" + this.index(i2 - 1);
    return str + ":" + this.parentOffset;
  }
  /**
  @internal
  */
  static resolve(doc3, pos) {
    if (!(pos >= 0 && pos <= doc3.content.size))
      throw new RangeError("Position " + pos + " out of range");
    let path = [];
    let start = 0, parentOffset = pos;
    for (let node2 = doc3; ; ) {
      let { index: index2, offset } = node2.content.findIndex(parentOffset);
      let rem = parentOffset - offset;
      path.push(node2, index2, start + offset);
      if (!rem)
        break;
      node2 = node2.child(index2);
      if (node2.isText)
        break;
      parentOffset = rem - 1;
      start += offset + 1;
    }
    return new _ResolvedPos(pos, path, parentOffset);
  }
  /**
  @internal
  */
  static resolveCached(doc3, pos) {
    let cache = resolveCache.get(doc3);
    if (cache) {
      for (let i2 = 0; i2 < cache.elts.length; i2++) {
        let elt = cache.elts[i2];
        if (elt.pos == pos)
          return elt;
      }
    } else {
      resolveCache.set(doc3, cache = new ResolveCache());
    }
    let result = cache.elts[cache.i] = _ResolvedPos.resolve(doc3, pos);
    cache.i = (cache.i + 1) % resolveCacheSize;
    return result;
  }
};
var ResolveCache = class {
  constructor() {
    this.elts = [];
    this.i = 0;
  }
};
var resolveCacheSize = 12;
var resolveCache = /* @__PURE__ */ new WeakMap();
var NodeRange = class {
  /**
  Construct a node range. `$from` and `$to` should point into the
  same node until at least the given `depth`, since a node range
  denotes an adjacent set of nodes in a single parent node.
  */
  constructor($from, $to, depth) {
    this.$from = $from;
    this.$to = $to;
    this.depth = depth;
  }
  /**
  The position at the start of the range.
  */
  get start() {
    return this.$from.before(this.depth + 1);
  }
  /**
  The position at the end of the range.
  */
  get end() {
    return this.$to.after(this.depth + 1);
  }
  /**
  The parent node that the range points into.
  */
  get parent() {
    return this.$from.node(this.depth);
  }
  /**
  The start index of the range in the parent node.
  */
  get startIndex() {
    return this.$from.index(this.depth);
  }
  /**
  The end index of the range in the parent node.
  */
  get endIndex() {
    return this.$to.indexAfter(this.depth);
  }
};
var emptyAttrs = /* @__PURE__ */ Object.create(null);
var Node = class _Node {
  /**
  @internal
  */
  constructor(type, attrs, content3, marks = Mark.none) {
    this.type = type;
    this.attrs = attrs;
    this.marks = marks;
    this.content = content3 || Fragment.empty;
  }
  /**
  The array of this node's child nodes.
  */
  get children() {
    return this.content.content;
  }
  /**
  The size of this node, as defined by the integer-based [indexing
  scheme](https://prosemirror.net/docs/guide/#doc.indexing). For text nodes, this is the
  amount of characters. For other leaf nodes, it is one. For
  non-leaf nodes, it is the size of the content plus two (the
  start and end token).
  */
  get nodeSize() {
    return this.isLeaf ? 1 : 2 + this.content.size;
  }
  /**
  The number of children that the node has.
  */
  get childCount() {
    return this.content.childCount;
  }
  /**
  Get the child node at the given index. Raises an error when the
  index is out of range.
  */
  child(index2) {
    return this.content.child(index2);
  }
  /**
  Get the child node at the given index, if it exists.
  */
  maybeChild(index2) {
    return this.content.maybeChild(index2);
  }
  /**
  Call `f` for every child node, passing the node, its offset
  into this parent node, and its index.
  */
  forEach(f) {
    this.content.forEach(f);
  }
  /**
  Invoke a callback for all descendant nodes recursively overlapping
  the given two positions that are relative to start of this
  node's content. This includes all ancestors of the nodes
  containing the two positions. The callback is invoked with the
  node, its position relative to the original node (method receiver),
  its parent node, and its child index. When the callback returns
  false for a given node, that node's children will not be
  recursed over. The last parameter can be used to specify a
  starting position to count from.
  */
  nodesBetween(from2, to, f, startPos = 0) {
    this.content.nodesBetween(from2, to, f, startPos, this);
  }
  /**
  Call the given callback for every descendant node. Doesn't
  descend into a node when the callback returns `false`.
  */
  descendants(f) {
    this.nodesBetween(0, this.content.size, f);
  }
  /**
  Concatenates all the text nodes found in this fragment and its
  children.
  */
  get textContent() {
    return this.isLeaf && this.type.spec.leafText ? this.type.spec.leafText(this) : this.textBetween(0, this.content.size, "");
  }
  /**
  Get all text between positions `from` and `to`. When
  `blockSeparator` is given, it will be inserted to separate text
  from different block nodes. If `leafText` is given, it'll be
  inserted for every non-text leaf node encountered, otherwise
  [`leafText`](https://prosemirror.net/docs/ref/#model.NodeSpec.leafText) will be used.
  */
  textBetween(from2, to, blockSeparator, leafText) {
    return this.content.textBetween(from2, to, blockSeparator, leafText);
  }
  /**
  Returns this node's first child, or `null` if there are no
  children.
  */
  get firstChild() {
    return this.content.firstChild;
  }
  /**
  Returns this node's last child, or `null` if there are no
  children.
  */
  get lastChild() {
    return this.content.lastChild;
  }
  /**
  Test whether two nodes represent the same piece of document.
  */
  eq(other) {
    return this == other || this.sameMarkup(other) && this.content.eq(other.content);
  }
  /**
  Compare the markup (type, attributes, and marks) of this node to
  those of another. Returns `true` if both have the same markup.
  */
  sameMarkup(other) {
    return this.hasMarkup(other.type, other.attrs, other.marks);
  }
  /**
  Check whether this node's markup correspond to the given type,
  attributes, and marks.
  */
  hasMarkup(type, attrs, marks) {
    return this.type == type && compareDeep(this.attrs, attrs || type.defaultAttrs || emptyAttrs) && Mark.sameSet(this.marks, marks || Mark.none);
  }
  /**
  Create a new node with the same markup as this node, containing
  the given content (or empty, if no content is given).
  */
  copy(content3 = null) {
    if (content3 == this.content)
      return this;
    return new _Node(this.type, this.attrs, content3, this.marks);
  }
  /**
  Create a copy of this node, with the given set of marks instead
  of the node's own marks.
  */
  mark(marks) {
    return marks == this.marks ? this : new _Node(this.type, this.attrs, this.content, marks);
  }
  /**
  Create a copy of this node with only the content between the
  given positions. If `to` is not given, it defaults to the end of
  the node.
  */
  cut(from2, to = this.content.size) {
    if (from2 == 0 && to == this.content.size)
      return this;
    return this.copy(this.content.cut(from2, to));
  }
  /**
  Cut out the part of the document between the given positions, and
  return it as a `Slice` object.
  */
  slice(from2, to = this.content.size, includeParents = false) {
    if (from2 == to)
      return Slice.empty;
    let $from = this.resolve(from2), $to = this.resolve(to);
    let depth = includeParents ? 0 : $from.sharedDepth(to);
    let start = $from.start(depth), node2 = $from.node(depth);
    let content3 = node2.content.cut($from.pos - start, $to.pos - start);
    return new Slice(content3, $from.depth - depth, $to.depth - depth);
  }
  /**
  Replace the part of the document between the given positions with
  the given slice. The slice must 'fit', meaning its open sides
  must be able to connect to the surrounding content, and its
  content nodes must be valid children for the node they are placed
  into. If any of this is violated, an error of type
  [`ReplaceError`](https://prosemirror.net/docs/ref/#model.ReplaceError) is thrown.
  */
  replace(from2, to, slice2) {
    return replace(this.resolve(from2), this.resolve(to), slice2);
  }
  /**
  Find the node directly after the given position.
  */
  nodeAt(pos) {
    for (let node2 = this; ; ) {
      let { index: index2, offset } = node2.content.findIndex(pos);
      node2 = node2.maybeChild(index2);
      if (!node2)
        return null;
      if (offset == pos || node2.isText)
        return node2;
      pos -= offset + 1;
    }
  }
  /**
  Find the (direct) child node after the given offset, if any,
  and return it along with its index and offset relative to this
  node.
  */
  childAfter(pos) {
    let { index: index2, offset } = this.content.findIndex(pos);
    return { node: this.content.maybeChild(index2), index: index2, offset };
  }
  /**
  Find the (direct) child node before the given offset, if any,
  and return it along with its index and offset relative to this
  node.
  */
  childBefore(pos) {
    if (pos == 0)
      return { node: null, index: 0, offset: 0 };
    let { index: index2, offset } = this.content.findIndex(pos);
    if (offset < pos)
      return { node: this.content.child(index2), index: index2, offset };
    let node2 = this.content.child(index2 - 1);
    return { node: node2, index: index2 - 1, offset: offset - node2.nodeSize };
  }
  /**
  Resolve the given position in the document, returning an
  [object](https://prosemirror.net/docs/ref/#model.ResolvedPos) with information about its context.
  */
  resolve(pos) {
    return ResolvedPos.resolveCached(this, pos);
  }
  /**
  @internal
  */
  resolveNoCache(pos) {
    return ResolvedPos.resolve(this, pos);
  }
  /**
  Test whether a given mark or mark type occurs in this document
  between the two given positions.
  */
  rangeHasMark(from2, to, type) {
    let found2 = false;
    if (to > from2)
      this.nodesBetween(from2, to, (node2) => {
        if (type.isInSet(node2.marks))
          found2 = true;
        return !found2;
      });
    return found2;
  }
  /**
  True when this is a block (non-inline node)
  */
  get isBlock() {
    return this.type.isBlock;
  }
  /**
  True when this is a textblock node, a block node with inline
  content.
  */
  get isTextblock() {
    return this.type.isTextblock;
  }
  /**
  True when this node allows inline content.
  */
  get inlineContent() {
    return this.type.inlineContent;
  }
  /**
  True when this is an inline node (a text node or a node that can
  appear among text).
  */
  get isInline() {
    return this.type.isInline;
  }
  /**
  True when this is a text node.
  */
  get isText() {
    return this.type.isText;
  }
  /**
  True when this is a leaf node.
  */
  get isLeaf() {
    return this.type.isLeaf;
  }
  /**
  True when this is an atom, i.e. when it does not have directly
  editable content. This is usually the same as `isLeaf`, but can
  be configured with the [`atom` property](https://prosemirror.net/docs/ref/#model.NodeSpec.atom)
  on a node's spec (typically used when the node is displayed as
  an uneditable [node view](https://prosemirror.net/docs/ref/#view.NodeView)).
  */
  get isAtom() {
    return this.type.isAtom;
  }
  /**
  Return a string representation of this node for debugging
  purposes.
  */
  toString() {
    if (this.type.spec.toDebugString)
      return this.type.spec.toDebugString(this);
    let name = this.type.name;
    if (this.content.size)
      name += "(" + this.content.toStringInner() + ")";
    return wrapMarks(this.marks, name);
  }
  /**
  Get the content match in this node at the given index.
  */
  contentMatchAt(index2) {
    let match = this.type.contentMatch.matchFragment(this.content, 0, index2);
    if (!match)
      throw new Error("Called contentMatchAt on a node with invalid content");
    return match;
  }
  /**
  Test whether replacing the range between `from` and `to` (by
  child index) with the given replacement fragment (which defaults
  to the empty fragment) would leave the node's content valid. You
  can optionally pass `start` and `end` indices into the
  replacement fragment.
  */
  canReplace(from2, to, replacement = Fragment.empty, start = 0, end = replacement.childCount) {
    let one2 = this.contentMatchAt(from2).matchFragment(replacement, start, end);
    let two = one2 && one2.matchFragment(this.content, to);
    if (!two || !two.validEnd)
      return false;
    for (let i2 = start; i2 < end; i2++)
      if (!this.type.allowsMarks(replacement.child(i2).marks))
        return false;
    return true;
  }
  /**
  Test whether replacing the range `from` to `to` (by index) with
  a node of the given type would leave the node's content valid.
  */
  canReplaceWith(from2, to, type, marks) {
    if (marks && !this.type.allowsMarks(marks))
      return false;
    let start = this.contentMatchAt(from2).matchType(type);
    let end = start && start.matchFragment(this.content, to);
    return end ? end.validEnd : false;
  }
  /**
  Test whether the given node's content could be appended to this
  node. If that node is empty, this will only return true if there
  is at least one node type that can appear in both nodes (to avoid
  merging completely incompatible nodes).
  */
  canAppend(other) {
    if (other.content.size)
      return this.canReplace(this.childCount, this.childCount, other.content);
    else
      return this.type.compatibleContent(other.type);
  }
  /**
  Check whether this node and its descendants conform to the
  schema, and raise an exception when they do not.
  */
  check() {
    this.type.checkContent(this.content);
    checkAttrs(this.type.attrs, this.attrs, "node", this.type.name);
    let copy2 = Mark.none;
    for (let i2 = 0; i2 < this.marks.length; i2++) {
      let mark = this.marks[i2];
      checkAttrs(mark.type.attrs, mark.attrs, "mark", mark.type.name);
      copy2 = mark.addToSet(copy2);
    }
    if (!Mark.sameSet(copy2, this.marks))
      throw new RangeError(`Invalid collection of marks for node ${this.type.name}: ${this.marks.map((m) => m.type.name)}`);
    this.content.forEach((node2) => node2.check());
  }
  /**
  Return a JSON-serializeable representation of this node.
  */
  toJSON() {
    let obj = { type: this.type.name };
    for (let _ in this.attrs) {
      obj.attrs = this.attrs;
      break;
    }
    if (this.content.size)
      obj.content = this.content.toJSON();
    if (this.marks.length)
      obj.marks = this.marks.map((n) => n.toJSON());
    return obj;
  }
  /**
  Deserialize a node from its JSON representation.
  */
  static fromJSON(schema2, json) {
    if (!json)
      throw new RangeError("Invalid input for Node.fromJSON");
    let marks = void 0;
    if (json.marks) {
      if (!Array.isArray(json.marks))
        throw new RangeError("Invalid mark data for Node.fromJSON");
      marks = json.marks.map(schema2.markFromJSON);
    }
    if (json.type == "text") {
      if (typeof json.text != "string")
        throw new RangeError("Invalid text node in JSON");
      return schema2.text(json.text, marks);
    }
    let content3 = Fragment.fromJSON(schema2, json.content);
    let node2 = schema2.nodeType(json.type).create(json.attrs, content3, marks);
    return node2;
  }
};
Node.prototype.text = void 0;
var TextNode = class _TextNode extends Node {
  /**
  @internal
  */
  constructor(type, attrs, content3, marks) {
    super(type, attrs, null, marks);
    if (!content3)
      throw new RangeError("Empty text nodes are not allowed");
    this.text = content3;
  }
  toString() {
    if (this.type.spec.toDebugString)
      return this.type.spec.toDebugString(this);
    return wrapMarks(this.marks, JSON.stringify(this.text));
  }
  get textContent() {
    return this.text;
  }
  textBetween(from2, to) {
    return this.text.slice(from2, to);
  }
  get nodeSize() {
    return this.text.length;
  }
  mark(marks) {
    return marks == this.marks ? this : new _TextNode(this.type, this.attrs, this.text, marks);
  }
  withText(text4) {
    if (text4 == this.text)
      return this;
    return new _TextNode(this.type, this.attrs, text4, this.marks);
  }
  cut(from2 = 0, to = this.text.length) {
    if (from2 == 0 && to == this.text.length)
      return this;
    return this.withText(this.text.slice(from2, to));
  }
  eq(other) {
    return this.sameMarkup(other) && this.text == other.text;
  }
  toJSON() {
    let base2 = super.toJSON();
    base2.text = this.text;
    return base2;
  }
};
function wrapMarks(marks, str) {
  for (let i2 = marks.length - 1; i2 >= 0; i2--)
    str = marks[i2].type.name + "(" + str + ")";
  return str;
}
function checkAttrs(attrs, values, type, name) {
  for (let attr in values)
    if (!(attr in attrs))
      throw new RangeError(`Unsupported attribute ${attr} for ${type} of type ${name}`);
  for (let attr in attrs) {
    if (attrs[attr].validate)
      attrs[attr].validate(values[attr]);
  }
}
var ContentMatch = class _ContentMatch {
  /**
  @internal
  */
  constructor(validEnd) {
    this.validEnd = validEnd;
    this.next = [];
    this.wrapCache = [];
  }
  /**
  @internal
  */
  static parse(string3, nodeTypes) {
    let stream = new TokenStream(string3, nodeTypes);
    if (stream.next == null)
      return _ContentMatch.empty;
    let expr = parseExpr(stream);
    if (stream.next)
      stream.err("Unexpected trailing text");
    let match = dfa(nfa(expr));
    checkForDeadEnds(match, stream);
    return match;
  }
  /**
  Match a node type, returning a match after that node if
  successful.
  */
  matchType(type) {
    for (let i2 = 0; i2 < this.next.length; i2++)
      if (this.next[i2].type == type)
        return this.next[i2].next;
    return null;
  }
  /**
  Try to match a fragment. Returns the resulting match when
  successful.
  */
  matchFragment(frag, start = 0, end = frag.childCount) {
    let cur = this;
    for (let i2 = start; cur && i2 < end; i2++)
      cur = cur.matchType(frag.child(i2).type);
    return cur;
  }
  /**
  @internal
  */
  get inlineContent() {
    return this.next.length != 0 && this.next[0].type.isInline;
  }
  /**
  Get the first matching node type at this match position that can
  be generated.
  */
  get defaultType() {
    for (let i2 = 0; i2 < this.next.length; i2++) {
      let { type } = this.next[i2];
      if (!(type.isText || type.hasRequiredAttrs()))
        return type;
    }
    return null;
  }
  /**
  @internal
  */
  compatible(other) {
    for (let i2 = 0; i2 < this.next.length; i2++)
      for (let j = 0; j < other.next.length; j++)
        if (this.next[i2].type == other.next[j].type)
          return true;
    return false;
  }
  /**
  Try to match the given fragment, and if that fails, see if it can
  be made to match by inserting nodes in front of it. When
  successful, return a fragment of inserted nodes (which may be
  empty if nothing had to be inserted). When `toEnd` is true, only
  return a fragment if the resulting match goes to the end of the
  content expression.
  */
  fillBefore(after, toEnd = false, startIndex = 0) {
    let seen = [this];
    function search2(match, types) {
      let finished = match.matchFragment(after, startIndex);
      if (finished && (!toEnd || finished.validEnd))
        return Fragment.from(types.map((tp) => tp.createAndFill()));
      for (let i2 = 0; i2 < match.next.length; i2++) {
        let { type, next } = match.next[i2];
        if (!(type.isText || type.hasRequiredAttrs()) && seen.indexOf(next) == -1) {
          seen.push(next);
          let found2 = search2(next, types.concat(type));
          if (found2)
            return found2;
        }
      }
      return null;
    }
    return search2(this, []);
  }
  /**
  Find a set of wrapping node types that would allow a node of the
  given type to appear at this position. The result may be empty
  (when it fits directly) and will be null when no such wrapping
  exists.
  */
  findWrapping(target) {
    for (let i2 = 0; i2 < this.wrapCache.length; i2 += 2)
      if (this.wrapCache[i2] == target)
        return this.wrapCache[i2 + 1];
    let computed = this.computeWrapping(target);
    this.wrapCache.push(target, computed);
    return computed;
  }
  /**
  @internal
  */
  computeWrapping(target) {
    let seen = /* @__PURE__ */ Object.create(null), active = [{ match: this, type: null, via: null }];
    while (active.length) {
      let current = active.shift(), match = current.match;
      if (match.matchType(target)) {
        let result = [];
        for (let obj = current; obj.type; obj = obj.via)
          result.push(obj.type);
        return result.reverse();
      }
      for (let i2 = 0; i2 < match.next.length; i2++) {
        let { type, next } = match.next[i2];
        if (!type.isLeaf && !type.hasRequiredAttrs() && !(type.name in seen) && (!current.type || next.validEnd)) {
          active.push({ match: type.contentMatch, type, via: current });
          seen[type.name] = true;
        }
      }
    }
    return null;
  }
  /**
  The number of outgoing edges this node has in the finite
  automaton that describes the content expression.
  */
  get edgeCount() {
    return this.next.length;
  }
  /**
  Get the _n_​th outgoing edge from this node in the finite
  automaton that describes the content expression.
  */
  edge(n) {
    if (n >= this.next.length)
      throw new RangeError(`There's no ${n}th edge in this content match`);
    return this.next[n];
  }
  /**
  @internal
  */
  toString() {
    let seen = [];
    function scan(m) {
      seen.push(m);
      for (let i2 = 0; i2 < m.next.length; i2++)
        if (seen.indexOf(m.next[i2].next) == -1)
          scan(m.next[i2].next);
    }
    scan(this);
    return seen.map((m, i2) => {
      let out = i2 + (m.validEnd ? "*" : " ") + " ";
      for (let i3 = 0; i3 < m.next.length; i3++)
        out += (i3 ? ", " : "") + m.next[i3].type.name + "->" + seen.indexOf(m.next[i3].next);
      return out;
    }).join("\n");
  }
};
ContentMatch.empty = new ContentMatch(true);
var TokenStream = class {
  constructor(string3, nodeTypes) {
    this.string = string3;
    this.nodeTypes = nodeTypes;
    this.inline = null;
    this.pos = 0;
    this.tokens = string3.split(/\s*(?=\b|\W|$)/);
    if (this.tokens[this.tokens.length - 1] == "")
      this.tokens.pop();
    if (this.tokens[0] == "")
      this.tokens.shift();
  }
  get next() {
    return this.tokens[this.pos];
  }
  eat(tok) {
    return this.next == tok && (this.pos++ || true);
  }
  err(str) {
    throw new SyntaxError(str + " (in content expression '" + this.string + "')");
  }
};
function parseExpr(stream) {
  let exprs = [];
  do {
    exprs.push(parseExprSeq(stream));
  } while (stream.eat("|"));
  return exprs.length == 1 ? exprs[0] : { type: "choice", exprs };
}
function parseExprSeq(stream) {
  let exprs = [];
  do {
    exprs.push(parseExprSubscript(stream));
  } while (stream.next && stream.next != ")" && stream.next != "|");
  return exprs.length == 1 ? exprs[0] : { type: "seq", exprs };
}
function parseExprSubscript(stream) {
  let expr = parseExprAtom(stream);
  for (; ; ) {
    if (stream.eat("+"))
      expr = { type: "plus", expr };
    else if (stream.eat("*"))
      expr = { type: "star", expr };
    else if (stream.eat("?"))
      expr = { type: "opt", expr };
    else if (stream.eat("{"))
      expr = parseExprRange(stream, expr);
    else
      break;
  }
  return expr;
}
function parseNum(stream) {
  if (/\D/.test(stream.next))
    stream.err("Expected number, got '" + stream.next + "'");
  let result = Number(stream.next);
  stream.pos++;
  return result;
}
function parseExprRange(stream, expr) {
  let min = parseNum(stream), max = min;
  if (stream.eat(",")) {
    if (stream.next != "}")
      max = parseNum(stream);
    else
      max = -1;
  }
  if (!stream.eat("}"))
    stream.err("Unclosed braced range");
  return { type: "range", min, max, expr };
}
function resolveName(stream, name) {
  let types = stream.nodeTypes, type = types[name];
  if (type)
    return [type];
  let result = [];
  for (let typeName in types) {
    let type2 = types[typeName];
    if (type2.isInGroup(name))
      result.push(type2);
  }
  if (result.length == 0)
    stream.err("No node type or group '" + name + "' found");
  return result;
}
function parseExprAtom(stream) {
  if (stream.eat("(")) {
    let expr = parseExpr(stream);
    if (!stream.eat(")"))
      stream.err("Missing closing paren");
    return expr;
  } else if (!/\W/.test(stream.next)) {
    let exprs = resolveName(stream, stream.next).map((type) => {
      if (stream.inline == null)
        stream.inline = type.isInline;
      else if (stream.inline != type.isInline)
        stream.err("Mixing inline and block content");
      return { type: "name", value: type };
    });
    stream.pos++;
    return exprs.length == 1 ? exprs[0] : { type: "choice", exprs };
  } else {
    stream.err("Unexpected token '" + stream.next + "'");
  }
}
function nfa(expr) {
  let nfa2 = [[]];
  connect(compile(expr, 0), node2());
  return nfa2;
  function node2() {
    return nfa2.push([]) - 1;
  }
  function edge(from2, to, term) {
    let edge2 = { term, to };
    nfa2[from2].push(edge2);
    return edge2;
  }
  function connect(edges, to) {
    edges.forEach((edge2) => edge2.to = to);
  }
  function compile(expr2, from2) {
    if (expr2.type == "choice") {
      return expr2.exprs.reduce((out, expr3) => out.concat(compile(expr3, from2)), []);
    } else if (expr2.type == "seq") {
      for (let i2 = 0; ; i2++) {
        let next = compile(expr2.exprs[i2], from2);
        if (i2 == expr2.exprs.length - 1)
          return next;
        connect(next, from2 = node2());
      }
    } else if (expr2.type == "star") {
      let loop = node2();
      edge(from2, loop);
      connect(compile(expr2.expr, loop), loop);
      return [edge(loop)];
    } else if (expr2.type == "plus") {
      let loop = node2();
      connect(compile(expr2.expr, from2), loop);
      connect(compile(expr2.expr, loop), loop);
      return [edge(loop)];
    } else if (expr2.type == "opt") {
      return [edge(from2)].concat(compile(expr2.expr, from2));
    } else if (expr2.type == "range") {
      let cur = from2;
      for (let i2 = 0; i2 < expr2.min; i2++) {
        let next = node2();
        connect(compile(expr2.expr, cur), next);
        cur = next;
      }
      if (expr2.max == -1) {
        connect(compile(expr2.expr, cur), cur);
      } else {
        for (let i2 = expr2.min; i2 < expr2.max; i2++) {
          let next = node2();
          edge(cur, next);
          connect(compile(expr2.expr, cur), next);
          cur = next;
        }
      }
      return [edge(cur)];
    } else if (expr2.type == "name") {
      return [edge(from2, void 0, expr2.value)];
    } else {
      throw new Error("Unknown expr type");
    }
  }
}
function cmp(a, b) {
  return b - a;
}
function nullFrom(nfa2, node2) {
  let result = [];
  scan(node2);
  return result.sort(cmp);
  function scan(node3) {
    let edges = nfa2[node3];
    if (edges.length == 1 && !edges[0].term)
      return scan(edges[0].to);
    result.push(node3);
    for (let i2 = 0; i2 < edges.length; i2++) {
      let { term, to } = edges[i2];
      if (!term && result.indexOf(to) == -1)
        scan(to);
    }
  }
}
function dfa(nfa2) {
  let labeled = /* @__PURE__ */ Object.create(null);
  return explore(nullFrom(nfa2, 0));
  function explore(states) {
    let out = [];
    states.forEach((node2) => {
      nfa2[node2].forEach(({ term, to }) => {
        if (!term)
          return;
        let set;
        for (let i2 = 0; i2 < out.length; i2++)
          if (out[i2][0] == term)
            set = out[i2][1];
        nullFrom(nfa2, to).forEach((node3) => {
          if (!set)
            out.push([term, set = []]);
          if (set.indexOf(node3) == -1)
            set.push(node3);
        });
      });
    });
    let state = labeled[states.join(",")] = new ContentMatch(states.indexOf(nfa2.length - 1) > -1);
    for (let i2 = 0; i2 < out.length; i2++) {
      let states2 = out[i2][1].sort(cmp);
      state.next.push({ type: out[i2][0], next: labeled[states2.join(",")] || explore(states2) });
    }
    return state;
  }
}
function checkForDeadEnds(match, stream) {
  for (let i2 = 0, work = [match]; i2 < work.length; i2++) {
    let state = work[i2], dead = !state.validEnd, nodes = [];
    for (let j = 0; j < state.next.length; j++) {
      let { type, next } = state.next[j];
      nodes.push(type.name);
      if (dead && !(type.isText || type.hasRequiredAttrs()))
        dead = false;
      if (work.indexOf(next) == -1)
        work.push(next);
    }
    if (dead)
      stream.err("Only non-generatable nodes (" + nodes.join(", ") + ") in a required position (see https://prosemirror.net/docs/guide/#generatable)");
  }
}
function defaultAttrs(attrs) {
  let defaults = /* @__PURE__ */ Object.create(null);
  for (let attrName in attrs) {
    let attr = attrs[attrName];
    if (!attr.hasDefault)
      return null;
    defaults[attrName] = attr.default;
  }
  return defaults;
}
function computeAttrs(attrs, value) {
  let built = /* @__PURE__ */ Object.create(null);
  for (let name in attrs) {
    let attr = attrs[name];
    let given = value && value[name];
    if (given === void 0) {
      if (attr.hasDefault)
        given = attr.default;
      else
        throw new RangeError("No value supplied for attribute " + name);
    } else if (attr.validate) {
      attr.validate(given);
    }
    built[name] = given;
  }
  return built;
}
function initAttrs(typeName, attrs) {
  let result = /* @__PURE__ */ Object.create(null);
  if (attrs)
    for (let name in attrs)
      result[name] = new Attribute(typeName, name, attrs[name]);
  return result;
}
var NodeType = class _NodeType {
  /**
  @internal
  */
  constructor(name, schema2, spec) {
    this.name = name;
    this.schema = schema2;
    this.spec = spec;
    this.markSet = null;
    this.groups = spec.group ? spec.group.split(" ") : [];
    this.attrs = initAttrs(name, spec.attrs);
    this.defaultAttrs = defaultAttrs(this.attrs);
    this.contentMatch = null;
    this.inlineContent = null;
    this.isBlock = !(spec.inline || name == "text");
    this.isText = name == "text";
  }
  /**
  True if this is an inline type.
  */
  get isInline() {
    return !this.isBlock;
  }
  /**
  True if this is a textblock type, a block that contains inline
  content.
  */
  get isTextblock() {
    return this.isBlock && this.inlineContent;
  }
  /**
  True for node types that allow no content.
  */
  get isLeaf() {
    return this.contentMatch == ContentMatch.empty;
  }
  /**
  True when this node is an atom, i.e. when it does not have
  directly editable content.
  */
  get isAtom() {
    return this.isLeaf || !!this.spec.atom;
  }
  /**
  Return true when this node type is part of the given
  [group](https://prosemirror.net/docs/ref/#model.NodeSpec.group).
  */
  isInGroup(group) {
    return this.groups.indexOf(group) > -1;
  }
  /**
  The node type's [whitespace](https://prosemirror.net/docs/ref/#model.NodeSpec.whitespace) option.
  */
  get whitespace() {
    return this.spec.whitespace || (this.spec.code ? "pre" : "normal");
  }
  /**
  Tells you whether this node type has any required attributes.
  */
  hasRequiredAttrs() {
    for (let n in this.attrs)
      if (this.attrs[n].isRequired)
        return true;
    return false;
  }
  /**
  Indicates whether this node allows some of the same content as
  the given node type.
  */
  compatibleContent(other) {
    return this == other || this.contentMatch.compatible(other.contentMatch);
  }
  /**
  @internal
  */
  computeAttrs(attrs) {
    if (!attrs && this.defaultAttrs)
      return this.defaultAttrs;
    else
      return computeAttrs(this.attrs, attrs);
  }
  /**
  Create a `Node` of this type. The given attributes are
  checked and defaulted (you can pass `null` to use the type's
  defaults entirely, if no required attributes exist). `content`
  may be a `Fragment`, a node, an array of nodes, or
  `null`. Similarly `marks` may be `null` to default to the empty
  set of marks.
  */
  create(attrs = null, content3, marks) {
    if (this.isText)
      throw new Error("NodeType.create can't construct text nodes");
    return new Node(this, this.computeAttrs(attrs), Fragment.from(content3), Mark.setFrom(marks));
  }
  /**
  Like [`create`](https://prosemirror.net/docs/ref/#model.NodeType.create), but check the given content
  against the node type's content restrictions, and throw an error
  if it doesn't match.
  */
  createChecked(attrs = null, content3, marks) {
    content3 = Fragment.from(content3);
    this.checkContent(content3);
    return new Node(this, this.computeAttrs(attrs), content3, Mark.setFrom(marks));
  }
  /**
  Like [`create`](https://prosemirror.net/docs/ref/#model.NodeType.create), but see if it is
  necessary to add nodes to the start or end of the given fragment
  to make it fit the node. If no fitting wrapping can be found,
  return null. Note that, due to the fact that required nodes can
  always be created, this will always succeed if you pass null or
  `Fragment.empty` as content.
  */
  createAndFill(attrs = null, content3, marks) {
    attrs = this.computeAttrs(attrs);
    content3 = Fragment.from(content3);
    if (content3.size) {
      let before = this.contentMatch.fillBefore(content3);
      if (!before)
        return null;
      content3 = before.append(content3);
    }
    let matched = this.contentMatch.matchFragment(content3);
    let after = matched && matched.fillBefore(Fragment.empty, true);
    if (!after)
      return null;
    return new Node(this, attrs, content3.append(after), Mark.setFrom(marks));
  }
  /**
  Returns true if the given fragment is valid content for this node
  type.
  */
  validContent(content3) {
    let result = this.contentMatch.matchFragment(content3);
    if (!result || !result.validEnd)
      return false;
    for (let i2 = 0; i2 < content3.childCount; i2++)
      if (!this.allowsMarks(content3.child(i2).marks))
        return false;
    return true;
  }
  /**
  Throws a RangeError if the given fragment is not valid content for this
  node type.
  @internal
  */
  checkContent(content3) {
    if (!this.validContent(content3))
      throw new RangeError(`Invalid content for node ${this.name}: ${content3.toString().slice(0, 50)}`);
  }
  /**
  @internal no longer useful, but called by old prosemirror-view versions
  */
  checkAttrs(attrs) {
  }
  /**
  Check whether the given mark type is allowed in this node.
  */
  allowsMarkType(markType) {
    return this.markSet == null || this.markSet.indexOf(markType) > -1;
  }
  /**
  Test whether the given set of marks are allowed in this node.
  */
  allowsMarks(marks) {
    if (this.markSet == null)
      return true;
    for (let i2 = 0; i2 < marks.length; i2++)
      if (!this.allowsMarkType(marks[i2].type))
        return false;
    return true;
  }
  /**
  Removes the marks that are not allowed in this node from the given set.
  */
  allowedMarks(marks) {
    if (this.markSet == null)
      return marks;
    let copy2;
    for (let i2 = 0; i2 < marks.length; i2++) {
      if (!this.allowsMarkType(marks[i2].type)) {
        if (!copy2)
          copy2 = marks.slice(0, i2);
      } else if (copy2) {
        copy2.push(marks[i2]);
      }
    }
    return !copy2 ? marks : copy2.length ? copy2 : Mark.none;
  }
  /**
  @internal
  */
  static compile(nodes, schema2) {
    let result = /* @__PURE__ */ Object.create(null);
    nodes.forEach((name, spec) => result[name] = new _NodeType(name, schema2, spec));
    let topType = schema2.spec.topNode || "doc";
    if (!result[topType])
      throw new RangeError("Schema is missing its top node type ('" + topType + "')");
    if (!result.text)
      throw new RangeError("Every schema needs a 'text' type");
    for (let _ in result.text.attrs)
      throw new RangeError("The text node type should not have attributes");
    return result;
  }
};
function validateType(typeName, attrName, type) {
  let types = type.split("|");
  return (value) => {
    let name = value === null ? "null" : typeof value;
    if (types.indexOf(name) < 0)
      throw new RangeError(`Expected value of type ${types} for attribute ${attrName} on type ${typeName}, got ${name}`);
  };
}
var Attribute = class {
  constructor(typeName, attrName, options) {
    this.hasDefault = Object.prototype.hasOwnProperty.call(options, "default");
    this.default = options.default;
    this.validate = typeof options.validate == "string" ? validateType(typeName, attrName, options.validate) : options.validate;
  }
  get isRequired() {
    return !this.hasDefault;
  }
};
var MarkType = class _MarkType {
  /**
  @internal
  */
  constructor(name, rank, schema2, spec) {
    this.name = name;
    this.rank = rank;
    this.schema = schema2;
    this.spec = spec;
    this.attrs = initAttrs(name, spec.attrs);
    this.excluded = null;
    let defaults = defaultAttrs(this.attrs);
    this.instance = defaults ? new Mark(this, defaults) : null;
  }
  /**
  Create a mark of this type. `attrs` may be `null` or an object
  containing only some of the mark's attributes. The others, if
  they have defaults, will be added.
  */
  create(attrs = null) {
    if (!attrs && this.instance)
      return this.instance;
    return new Mark(this, computeAttrs(this.attrs, attrs));
  }
  /**
  @internal
  */
  static compile(marks, schema2) {
    let result = /* @__PURE__ */ Object.create(null), rank = 0;
    marks.forEach((name, spec) => result[name] = new _MarkType(name, rank++, schema2, spec));
    return result;
  }
  /**
  When there is a mark of this type in the given set, a new set
  without it is returned. Otherwise, the input set is returned.
  */
  removeFromSet(set) {
    for (var i2 = 0; i2 < set.length; i2++)
      if (set[i2].type == this) {
        set = set.slice(0, i2).concat(set.slice(i2 + 1));
        i2--;
      }
    return set;
  }
  /**
  Tests whether there is a mark of this type in the given set.
  */
  isInSet(set) {
    for (let i2 = 0; i2 < set.length; i2++)
      if (set[i2].type == this)
        return set[i2];
  }
  /**
  Queries whether a given mark type is
  [excluded](https://prosemirror.net/docs/ref/#model.MarkSpec.excludes) by this one.
  */
  excludes(other) {
    return this.excluded.indexOf(other) > -1;
  }
};
var Schema = class {
  /**
  Construct a schema from a schema [specification](https://prosemirror.net/docs/ref/#model.SchemaSpec).
  */
  constructor(spec) {
    this.linebreakReplacement = null;
    this.cached = /* @__PURE__ */ Object.create(null);
    let instanceSpec = this.spec = {};
    for (let prop in spec)
      instanceSpec[prop] = spec[prop];
    instanceSpec.nodes = dist_default.from(spec.nodes), instanceSpec.marks = dist_default.from(spec.marks || {}), this.nodes = NodeType.compile(this.spec.nodes, this);
    this.marks = MarkType.compile(this.spec.marks, this);
    let contentExprCache = /* @__PURE__ */ Object.create(null);
    for (let prop in this.nodes) {
      if (prop in this.marks)
        throw new RangeError(prop + " can not be both a node and a mark");
      let type = this.nodes[prop], contentExpr = type.spec.content || "", markExpr = type.spec.marks;
      type.contentMatch = contentExprCache[contentExpr] || (contentExprCache[contentExpr] = ContentMatch.parse(contentExpr, this.nodes));
      type.inlineContent = type.contentMatch.inlineContent;
      if (type.spec.linebreakReplacement) {
        if (this.linebreakReplacement)
          throw new RangeError("Multiple linebreak nodes defined");
        if (!type.isInline || !type.isLeaf)
          throw new RangeError("Linebreak replacement nodes must be inline leaf nodes");
        this.linebreakReplacement = type;
      }
      type.markSet = markExpr == "_" ? null : markExpr ? gatherMarks(this, markExpr.split(" ")) : markExpr == "" || !type.inlineContent ? [] : null;
    }
    for (let prop in this.marks) {
      let type = this.marks[prop], excl = type.spec.excludes;
      type.excluded = excl == null ? [type] : excl == "" ? [] : gatherMarks(this, excl.split(" "));
    }
    this.nodeFromJSON = (json) => Node.fromJSON(this, json);
    this.markFromJSON = (json) => Mark.fromJSON(this, json);
    this.topNodeType = this.nodes[this.spec.topNode || "doc"];
    this.cached.wrappings = /* @__PURE__ */ Object.create(null);
  }
  /**
  Create a node in this schema. The `type` may be a string or a
  `NodeType` instance. Attributes will be extended with defaults,
  `content` may be a `Fragment`, `null`, a `Node`, or an array of
  nodes.
  */
  node(type, attrs = null, content3, marks) {
    if (typeof type == "string")
      type = this.nodeType(type);
    else if (!(type instanceof NodeType))
      throw new RangeError("Invalid node type: " + type);
    else if (type.schema != this)
      throw new RangeError("Node type from different schema used (" + type.name + ")");
    return type.createChecked(attrs, content3, marks);
  }
  /**
  Create a text node in the schema. Empty text nodes are not
  allowed.
  */
  text(text4, marks) {
    let type = this.nodes.text;
    return new TextNode(type, type.defaultAttrs, text4, Mark.setFrom(marks));
  }
  /**
  Create a mark with the given type and attributes.
  */
  mark(type, attrs) {
    if (typeof type == "string")
      type = this.marks[type];
    return type.create(attrs);
  }
  /**
  @internal
  */
  nodeType(name) {
    let found2 = this.nodes[name];
    if (!found2)
      throw new RangeError("Unknown node type: " + name);
    return found2;
  }
};
function gatherMarks(schema2, marks) {
  let found2 = [];
  for (let i2 = 0; i2 < marks.length; i2++) {
    let name = marks[i2], mark = schema2.marks[name], ok2 = mark;
    if (mark) {
      found2.push(mark);
    } else {
      for (let prop in schema2.marks) {
        let mark2 = schema2.marks[prop];
        if (name == "_" || mark2.spec.group && mark2.spec.group.split(" ").indexOf(name) > -1)
          found2.push(ok2 = mark2);
      }
    }
    if (!ok2)
      throw new SyntaxError("Unknown mark type: '" + marks[i2] + "'");
  }
  return found2;
}
function isTagRule(rule) {
  return rule.tag != null;
}
function isStyleRule(rule) {
  return rule.style != null;
}
var DOMParser = class _DOMParser {
  /**
  Create a parser that targets the given schema, using the given
  parsing rules.
  */
  constructor(schema2, rules) {
    this.schema = schema2;
    this.rules = rules;
    this.tags = [];
    this.styles = [];
    let matchedStyles = this.matchedStyles = [];
    rules.forEach((rule) => {
      if (isTagRule(rule)) {
        this.tags.push(rule);
      } else if (isStyleRule(rule)) {
        let prop = /[^=]*/.exec(rule.style)[0];
        if (matchedStyles.indexOf(prop) < 0)
          matchedStyles.push(prop);
        this.styles.push(rule);
      }
    });
    this.normalizeLists = !this.tags.some((r) => {
      if (!/^(ul|ol)\b/.test(r.tag) || !r.node)
        return false;
      let node2 = schema2.nodes[r.node];
      return node2.contentMatch.matchType(node2);
    });
  }
  /**
  Parse a document from the content of a DOM node.
  */
  parse(dom, options = {}) {
    let context = new ParseContext(this, options, false);
    context.addAll(dom, Mark.none, options.from, options.to);
    return context.finish();
  }
  /**
  Parses the content of the given DOM node, like
  [`parse`](https://prosemirror.net/docs/ref/#model.DOMParser.parse), and takes the same set of
  options. But unlike that method, which produces a whole node,
  this one returns a slice that is open at the sides, meaning that
  the schema constraints aren't applied to the start of nodes to
  the left of the input and the end of nodes at the end.
  */
  parseSlice(dom, options = {}) {
    let context = new ParseContext(this, options, true);
    context.addAll(dom, Mark.none, options.from, options.to);
    return Slice.maxOpen(context.finish());
  }
  /**
  @internal
  */
  matchTag(dom, context, after) {
    for (let i2 = after ? this.tags.indexOf(after) + 1 : 0; i2 < this.tags.length; i2++) {
      let rule = this.tags[i2];
      if (matches(dom, rule.tag) && (rule.namespace === void 0 || dom.namespaceURI == rule.namespace) && (!rule.context || context.matchesContext(rule.context))) {
        if (rule.getAttrs) {
          let result = rule.getAttrs(dom);
          if (result === false)
            continue;
          rule.attrs = result || void 0;
        }
        return rule;
      }
    }
  }
  /**
  @internal
  */
  matchStyle(prop, value, context, after) {
    for (let i2 = after ? this.styles.indexOf(after) + 1 : 0; i2 < this.styles.length; i2++) {
      let rule = this.styles[i2], style = rule.style;
      if (style.indexOf(prop) != 0 || rule.context && !context.matchesContext(rule.context) || // Test that the style string either precisely matches the prop,
      // or has an '=' sign after the prop, followed by the given
      // value.
      style.length > prop.length && (style.charCodeAt(prop.length) != 61 || style.slice(prop.length + 1) != value))
        continue;
      if (rule.getAttrs) {
        let result = rule.getAttrs(value);
        if (result === false)
          continue;
        rule.attrs = result || void 0;
      }
      return rule;
    }
  }
  /**
  @internal
  */
  static schemaRules(schema2) {
    let result = [];
    function insert(rule) {
      let priority = rule.priority == null ? 50 : rule.priority, i2 = 0;
      for (; i2 < result.length; i2++) {
        let next = result[i2], nextPriority = next.priority == null ? 50 : next.priority;
        if (nextPriority < priority)
          break;
      }
      result.splice(i2, 0, rule);
    }
    for (let name in schema2.marks) {
      let rules = schema2.marks[name].spec.parseDOM;
      if (rules)
        rules.forEach((rule) => {
          insert(rule = copy(rule));
          if (!(rule.mark || rule.ignore || rule.clearMark))
            rule.mark = name;
        });
    }
    for (let name in schema2.nodes) {
      let rules = schema2.nodes[name].spec.parseDOM;
      if (rules)
        rules.forEach((rule) => {
          insert(rule = copy(rule));
          if (!(rule.node || rule.ignore || rule.mark))
            rule.node = name;
        });
    }
    return result;
  }
  /**
  Construct a DOM parser using the parsing rules listed in a
  schema's [node specs](https://prosemirror.net/docs/ref/#model.NodeSpec.parseDOM), reordered by
  [priority](https://prosemirror.net/docs/ref/#model.GenericParseRule.priority).
  */
  static fromSchema(schema2) {
    return schema2.cached.domParser || (schema2.cached.domParser = new _DOMParser(schema2, _DOMParser.schemaRules(schema2)));
  }
};
var blockTags = {
  address: true,
  article: true,
  aside: true,
  blockquote: true,
  body: true,
  canvas: true,
  dd: true,
  div: true,
  dl: true,
  fieldset: true,
  figcaption: true,
  figure: true,
  footer: true,
  form: true,
  h1: true,
  h2: true,
  h3: true,
  h4: true,
  h5: true,
  h6: true,
  header: true,
  hgroup: true,
  hr: true,
  li: true,
  noscript: true,
  ol: true,
  output: true,
  p: true,
  pre: true,
  section: true,
  table: true,
  tfoot: true,
  ul: true
};
var ignoreTags = {
  head: true,
  noscript: true,
  object: true,
  script: true,
  style: true,
  title: true
};
var listTags = { ol: true, ul: true };
var OPT_PRESERVE_WS = 1;
var OPT_PRESERVE_WS_FULL = 2;
var OPT_OPEN_LEFT = 4;
function wsOptionsFor(type, preserveWhitespace, base2) {
  if (preserveWhitespace != null)
    return (preserveWhitespace ? OPT_PRESERVE_WS : 0) | (preserveWhitespace === "full" ? OPT_PRESERVE_WS_FULL : 0);
  return type && type.whitespace == "pre" ? OPT_PRESERVE_WS | OPT_PRESERVE_WS_FULL : base2 & ~OPT_OPEN_LEFT;
}
var NodeContext = class {
  constructor(type, attrs, marks, solid, match, options) {
    this.type = type;
    this.attrs = attrs;
    this.marks = marks;
    this.solid = solid;
    this.options = options;
    this.content = [];
    this.activeMarks = Mark.none;
    this.match = match || (options & OPT_OPEN_LEFT ? null : type.contentMatch);
  }
  findWrapping(node2) {
    if (!this.match) {
      if (!this.type)
        return [];
      let fill = this.type.contentMatch.fillBefore(Fragment.from(node2));
      if (fill) {
        this.match = this.type.contentMatch.matchFragment(fill);
      } else {
        let start = this.type.contentMatch, wrap2;
        if (wrap2 = start.findWrapping(node2.type)) {
          this.match = start;
          return wrap2;
        } else {
          return null;
        }
      }
    }
    return this.match.findWrapping(node2.type);
  }
  finish(openEnd) {
    if (!(this.options & OPT_PRESERVE_WS)) {
      let last = this.content[this.content.length - 1], m;
      if (last && last.isText && (m = /[ \t\r\n\u000c]+$/.exec(last.text))) {
        let text4 = last;
        if (last.text.length == m[0].length)
          this.content.pop();
        else
          this.content[this.content.length - 1] = text4.withText(text4.text.slice(0, text4.text.length - m[0].length));
      }
    }
    let content3 = Fragment.from(this.content);
    if (!openEnd && this.match)
      content3 = content3.append(this.match.fillBefore(Fragment.empty, true));
    return this.type ? this.type.create(this.attrs, content3, this.marks) : content3;
  }
  inlineContext(node2) {
    if (this.type)
      return this.type.inlineContent;
    if (this.content.length)
      return this.content[0].isInline;
    return node2.parentNode && !blockTags.hasOwnProperty(node2.parentNode.nodeName.toLowerCase());
  }
};
var ParseContext = class {
  constructor(parser, options, isOpen) {
    this.parser = parser;
    this.options = options;
    this.isOpen = isOpen;
    this.open = 0;
    this.localPreserveWS = false;
    let topNode = options.topNode, topContext;
    let topOptions = wsOptionsFor(null, options.preserveWhitespace, 0) | (isOpen ? OPT_OPEN_LEFT : 0);
    if (topNode)
      topContext = new NodeContext(topNode.type, topNode.attrs, Mark.none, true, options.topMatch || topNode.type.contentMatch, topOptions);
    else if (isOpen)
      topContext = new NodeContext(null, null, Mark.none, true, null, topOptions);
    else
      topContext = new NodeContext(parser.schema.topNodeType, null, Mark.none, true, null, topOptions);
    this.nodes = [topContext];
    this.find = options.findPositions;
    this.needsBlock = false;
  }
  get top() {
    return this.nodes[this.open];
  }
  // Add a DOM node to the content. Text is inserted as text node,
  // otherwise, the node is passed to `addElement` or, if it has a
  // `style` attribute, `addElementWithStyles`.
  addDOM(dom, marks) {
    if (dom.nodeType == 3)
      this.addTextNode(dom, marks);
    else if (dom.nodeType == 1)
      this.addElement(dom, marks);
  }
  addTextNode(dom, marks) {
    let value = dom.nodeValue;
    let top = this.top, preserveWS = top.options & OPT_PRESERVE_WS_FULL ? "full" : this.localPreserveWS || (top.options & OPT_PRESERVE_WS) > 0;
    let { schema: schema2 } = this.parser;
    if (preserveWS === "full" || top.inlineContext(dom) || /[^ \t\r\n\u000c]/.test(value)) {
      if (!preserveWS) {
        value = value.replace(/[ \t\r\n\u000c]+/g, " ");
        if (/^[ \t\r\n\u000c]/.test(value) && this.open == this.nodes.length - 1) {
          let nodeBefore = top.content[top.content.length - 1];
          let domNodeBefore = dom.previousSibling;
          if (!nodeBefore || domNodeBefore && domNodeBefore.nodeName == "BR" || nodeBefore.isText && /[ \t\r\n\u000c]$/.test(nodeBefore.text))
            value = value.slice(1);
        }
      } else if (preserveWS === "full") {
        value = value.replace(/\r\n?/g, "\n");
      } else if (schema2.linebreakReplacement && /[\r\n]/.test(value) && this.top.findWrapping(schema2.linebreakReplacement.create())) {
        let lines = value.split(/\r?\n|\r/);
        for (let i2 = 0; i2 < lines.length; i2++) {
          if (i2)
            this.insertNode(schema2.linebreakReplacement.create(), marks, true);
          if (lines[i2])
            this.insertNode(schema2.text(lines[i2]), marks, !/\S/.test(lines[i2]));
        }
        value = "";
      } else {
        value = value.replace(/\r?\n|\r/g, " ");
      }
      if (value)
        this.insertNode(schema2.text(value), marks, !/\S/.test(value));
      this.findInText(dom);
    } else {
      this.findInside(dom);
    }
  }
  // Try to find a handler for the given tag and use that to parse. If
  // none is found, the element's content nodes are added directly.
  addElement(dom, marks, matchAfter) {
    let outerWS = this.localPreserveWS, top = this.top;
    if (dom.tagName == "PRE" || /pre/.test(dom.style && dom.style.whiteSpace))
      this.localPreserveWS = true;
    let name = dom.nodeName.toLowerCase(), ruleID;
    if (listTags.hasOwnProperty(name) && this.parser.normalizeLists)
      normalizeList(dom);
    let rule = this.options.ruleFromNode && this.options.ruleFromNode(dom) || (ruleID = this.parser.matchTag(dom, this, matchAfter));
    out: if (rule ? rule.ignore : ignoreTags.hasOwnProperty(name)) {
      this.findInside(dom);
      this.ignoreFallback(dom, marks);
    } else if (!rule || rule.skip || rule.closeParent) {
      if (rule && rule.closeParent)
        this.open = Math.max(0, this.open - 1);
      else if (rule && rule.skip.nodeType)
        dom = rule.skip;
      let sync, oldNeedsBlock = this.needsBlock;
      if (blockTags.hasOwnProperty(name)) {
        if (top.content.length && top.content[0].isInline && this.open) {
          this.open--;
          top = this.top;
        }
        sync = true;
        if (!top.type)
          this.needsBlock = true;
      } else if (!dom.firstChild) {
        this.leafFallback(dom, marks);
        break out;
      }
      let innerMarks = rule && rule.skip ? marks : this.readStyles(dom, marks);
      if (innerMarks)
        this.addAll(dom, innerMarks);
      if (sync)
        this.sync(top);
      this.needsBlock = oldNeedsBlock;
    } else {
      let innerMarks = this.readStyles(dom, marks);
      if (innerMarks)
        this.addElementByRule(dom, rule, innerMarks, rule.consuming === false ? ruleID : void 0);
    }
    this.localPreserveWS = outerWS;
  }
  // Called for leaf DOM nodes that would otherwise be ignored
  leafFallback(dom, marks) {
    if (dom.nodeName == "BR" && this.top.type && this.top.type.inlineContent)
      this.addTextNode(dom.ownerDocument.createTextNode("\n"), marks);
  }
  // Called for ignored nodes
  ignoreFallback(dom, marks) {
    if (dom.nodeName == "BR" && (!this.top.type || !this.top.type.inlineContent))
      this.findPlace(this.parser.schema.text("-"), marks, true);
  }
  // Run any style parser associated with the node's styles. Either
  // return an updated array of marks, or null to indicate some of the
  // styles had a rule with `ignore` set.
  readStyles(dom, marks) {
    let styles = dom.style;
    if (styles && styles.length)
      for (let i2 = 0; i2 < this.parser.matchedStyles.length; i2++) {
        let name = this.parser.matchedStyles[i2], value = styles.getPropertyValue(name);
        if (value)
          for (let after = void 0; ; ) {
            let rule = this.parser.matchStyle(name, value, this, after);
            if (!rule)
              break;
            if (rule.ignore)
              return null;
            if (rule.clearMark)
              marks = marks.filter((m) => !rule.clearMark(m));
            else
              marks = marks.concat(this.parser.schema.marks[rule.mark].create(rule.attrs));
            if (rule.consuming === false)
              after = rule;
            else
              break;
          }
      }
    return marks;
  }
  // Look up a handler for the given node. If none are found, return
  // false. Otherwise, apply it, use its return value to drive the way
  // the node's content is wrapped, and return true.
  addElementByRule(dom, rule, marks, continueAfter) {
    let sync, nodeType;
    if (rule.node) {
      nodeType = this.parser.schema.nodes[rule.node];
      if (!nodeType.isLeaf) {
        let inner = this.enter(nodeType, rule.attrs || null, marks, rule.preserveWhitespace);
        if (inner) {
          sync = true;
          marks = inner;
        }
      } else if (!this.insertNode(nodeType.create(rule.attrs), marks, dom.nodeName == "BR")) {
        this.leafFallback(dom, marks);
      }
    } else {
      let markType = this.parser.schema.marks[rule.mark];
      marks = marks.concat(markType.create(rule.attrs));
    }
    let startIn = this.top;
    if (nodeType && nodeType.isLeaf) {
      this.findInside(dom);
    } else if (continueAfter) {
      this.addElement(dom, marks, continueAfter);
    } else if (rule.getContent) {
      this.findInside(dom);
      rule.getContent(dom, this.parser.schema).forEach((node2) => this.insertNode(node2, marks, false));
    } else {
      let contentDOM = dom;
      if (typeof rule.contentElement == "string")
        contentDOM = dom.querySelector(rule.contentElement);
      else if (typeof rule.contentElement == "function")
        contentDOM = rule.contentElement(dom);
      else if (rule.contentElement)
        contentDOM = rule.contentElement;
      this.findAround(dom, contentDOM, true);
      this.addAll(contentDOM, marks);
      this.findAround(dom, contentDOM, false);
    }
    if (sync && this.sync(startIn))
      this.open--;
  }
  // Add all child nodes between `startIndex` and `endIndex` (or the
  // whole node, if not given). If `sync` is passed, use it to
  // synchronize after every block element.
  addAll(parent, marks, startIndex, endIndex) {
    let index2 = startIndex || 0;
    for (let dom = startIndex ? parent.childNodes[startIndex] : parent.firstChild, end = endIndex == null ? null : parent.childNodes[endIndex]; dom != end; dom = dom.nextSibling, ++index2) {
      this.findAtPoint(parent, index2);
      this.addDOM(dom, marks);
    }
    this.findAtPoint(parent, index2);
  }
  // Try to find a way to fit the given node type into the current
  // context. May add intermediate wrappers and/or leave non-solid
  // nodes that we're in.
  findPlace(node2, marks, cautious) {
    let route, sync;
    for (let depth = this.open, penalty = 0; depth >= 0; depth--) {
      let cx = this.nodes[depth];
      let found2 = cx.findWrapping(node2);
      if (found2 && (!route || route.length > found2.length + penalty)) {
        route = found2;
        sync = cx;
        if (!found2.length)
          break;
      }
      if (cx.solid) {
        if (cautious)
          break;
        penalty += 2;
      }
    }
    if (!route)
      return null;
    this.sync(sync);
    for (let i2 = 0; i2 < route.length; i2++)
      marks = this.enterInner(route[i2], null, marks, false);
    return marks;
  }
  // Try to insert the given node, adjusting the context when needed.
  insertNode(node2, marks, cautious) {
    if (node2.isInline && this.needsBlock && !this.top.type) {
      let block = this.textblockFromContext();
      if (block)
        marks = this.enterInner(block, null, marks);
    }
    let innerMarks = this.findPlace(node2, marks, cautious);
    if (innerMarks) {
      this.closeExtra();
      let top = this.top;
      if (top.match)
        top.match = top.match.matchType(node2.type);
      let nodeMarks = Mark.none;
      for (let m of innerMarks.concat(node2.marks))
        if (top.type ? top.type.allowsMarkType(m.type) : markMayApply(m.type, node2.type))
          nodeMarks = m.addToSet(nodeMarks);
      top.content.push(node2.mark(nodeMarks));
      return true;
    }
    return false;
  }
  // Try to start a node of the given type, adjusting the context when
  // necessary.
  enter(type, attrs, marks, preserveWS) {
    let innerMarks = this.findPlace(type.create(attrs), marks, false);
    if (innerMarks)
      innerMarks = this.enterInner(type, attrs, marks, true, preserveWS);
    return innerMarks;
  }
  // Open a node of the given type
  enterInner(type, attrs, marks, solid = false, preserveWS) {
    this.closeExtra();
    let top = this.top;
    top.match = top.match && top.match.matchType(type);
    let options = wsOptionsFor(type, preserveWS, top.options);
    if (top.options & OPT_OPEN_LEFT && top.content.length == 0)
      options |= OPT_OPEN_LEFT;
    let applyMarks = Mark.none;
    marks = marks.filter((m) => {
      if (top.type ? top.type.allowsMarkType(m.type) : markMayApply(m.type, type)) {
        applyMarks = m.addToSet(applyMarks);
        return false;
      }
      return true;
    });
    this.nodes.push(new NodeContext(type, attrs, applyMarks, solid, null, options));
    this.open++;
    return marks;
  }
  // Make sure all nodes above this.open are finished and added to
  // their parents
  closeExtra(openEnd = false) {
    let i2 = this.nodes.length - 1;
    if (i2 > this.open) {
      for (; i2 > this.open; i2--)
        this.nodes[i2 - 1].content.push(this.nodes[i2].finish(openEnd));
      this.nodes.length = this.open + 1;
    }
  }
  finish() {
    this.open = 0;
    this.closeExtra(this.isOpen);
    return this.nodes[0].finish(!!(this.isOpen || this.options.topOpen));
  }
  sync(to) {
    for (let i2 = this.open; i2 >= 0; i2--) {
      if (this.nodes[i2] == to) {
        this.open = i2;
        return true;
      } else if (this.localPreserveWS) {
        this.nodes[i2].options |= OPT_PRESERVE_WS;
      }
    }
    return false;
  }
  get currentPos() {
    this.closeExtra();
    let pos = 0;
    for (let i2 = this.open; i2 >= 0; i2--) {
      let content3 = this.nodes[i2].content;
      for (let j = content3.length - 1; j >= 0; j--)
        pos += content3[j].nodeSize;
      if (i2)
        pos++;
    }
    return pos;
  }
  findAtPoint(parent, offset) {
    if (this.find)
      for (let i2 = 0; i2 < this.find.length; i2++) {
        if (this.find[i2].node == parent && this.find[i2].offset == offset)
          this.find[i2].pos = this.currentPos;
      }
  }
  findInside(parent) {
    if (this.find)
      for (let i2 = 0; i2 < this.find.length; i2++) {
        if (this.find[i2].pos == null && parent.nodeType == 1 && parent.contains(this.find[i2].node))
          this.find[i2].pos = this.currentPos;
      }
  }
  findAround(parent, content3, before) {
    if (parent != content3 && this.find)
      for (let i2 = 0; i2 < this.find.length; i2++) {
        if (this.find[i2].pos == null && parent.nodeType == 1 && parent.contains(this.find[i2].node)) {
          let pos = content3.compareDocumentPosition(this.find[i2].node);
          if (pos & (before ? 2 : 4))
            this.find[i2].pos = this.currentPos;
        }
      }
  }
  findInText(textNode) {
    if (this.find)
      for (let i2 = 0; i2 < this.find.length; i2++) {
        if (this.find[i2].node == textNode)
          this.find[i2].pos = this.currentPos - (textNode.nodeValue.length - this.find[i2].offset);
      }
  }
  // Determines whether the given context string matches this context.
  matchesContext(context) {
    if (context.indexOf("|") > -1)
      return context.split(/\s*\|\s*/).some(this.matchesContext, this);
    let parts = context.split("/");
    let option = this.options.context;
    let useRoot = !this.isOpen && (!option || option.parent.type == this.nodes[0].type);
    let minDepth = -(option ? option.depth + 1 : 0) + (useRoot ? 0 : 1);
    let match = (i2, depth) => {
      for (; i2 >= 0; i2--) {
        let part = parts[i2];
        if (part == "") {
          if (i2 == parts.length - 1 || i2 == 0)
            continue;
          for (; depth >= minDepth; depth--)
            if (match(i2 - 1, depth))
              return true;
          return false;
        } else {
          let next = depth > 0 || depth == 0 && useRoot ? this.nodes[depth].type : option && depth >= minDepth ? option.node(depth - minDepth).type : null;
          if (!next || next.name != part && !next.isInGroup(part))
            return false;
          depth--;
        }
      }
      return true;
    };
    return match(parts.length - 1, this.open);
  }
  textblockFromContext() {
    let $context = this.options.context;
    if ($context)
      for (let d = $context.depth; d >= 0; d--) {
        let deflt = $context.node(d).contentMatchAt($context.indexAfter(d)).defaultType;
        if (deflt && deflt.isTextblock && deflt.defaultAttrs)
          return deflt;
      }
    for (let name in this.parser.schema.nodes) {
      let type = this.parser.schema.nodes[name];
      if (type.isTextblock && type.defaultAttrs)
        return type;
    }
  }
};
function normalizeList(dom) {
  for (let child = dom.firstChild, prevItem = null; child; child = child.nextSibling) {
    let name = child.nodeType == 1 ? child.nodeName.toLowerCase() : null;
    if (name && listTags.hasOwnProperty(name) && prevItem) {
      prevItem.appendChild(child);
      child = prevItem;
    } else if (name == "li") {
      prevItem = child;
    } else if (name) {
      prevItem = null;
    }
  }
}
function matches(dom, selector) {
  return (dom.matches || dom.msMatchesSelector || dom.webkitMatchesSelector || dom.mozMatchesSelector).call(dom, selector);
}
function copy(obj) {
  let copy2 = {};
  for (let prop in obj)
    copy2[prop] = obj[prop];
  return copy2;
}
function markMayApply(markType, nodeType) {
  let nodes = nodeType.schema.nodes;
  for (let name in nodes) {
    let parent = nodes[name];
    if (!parent.allowsMarkType(markType))
      continue;
    let seen = [], scan = (match) => {
      seen.push(match);
      for (let i2 = 0; i2 < match.edgeCount; i2++) {
        let { type, next } = match.edge(i2);
        if (type == nodeType)
          return true;
        if (seen.indexOf(next) < 0 && scan(next))
          return true;
      }
    };
    if (scan(parent.contentMatch))
      return true;
  }
}
var DOMSerializer = class _DOMSerializer {
  /**
  Create a serializer. `nodes` should map node names to functions
  that take a node and return a description of the corresponding
  DOM. `marks` does the same for mark names, but also gets an
  argument that tells it whether the mark's content is block or
  inline content (for typical use, it'll always be inline). A mark
  serializer may be `null` to indicate that marks of that type
  should not be serialized.
  */
  constructor(nodes, marks) {
    this.nodes = nodes;
    this.marks = marks;
  }
  /**
  Serialize the content of this fragment to a DOM fragment. When
  not in the browser, the `document` option, containing a DOM
  document, should be passed so that the serializer can create
  nodes.
  */
  serializeFragment(fragment, options = {}, target) {
    if (!target)
      target = doc(options).createDocumentFragment();
    let top = target, active = [];
    fragment.forEach((node2) => {
      if (active.length || node2.marks.length) {
        let keep = 0, rendered = 0;
        while (keep < active.length && rendered < node2.marks.length) {
          let next = node2.marks[rendered];
          if (!this.marks[next.type.name]) {
            rendered++;
            continue;
          }
          if (!next.eq(active[keep][0]) || next.type.spec.spanning === false)
            break;
          keep++;
          rendered++;
        }
        while (keep < active.length)
          top = active.pop()[1];
        while (rendered < node2.marks.length) {
          let add = node2.marks[rendered++];
          let markDOM = this.serializeMark(add, node2.isInline, options);
          if (markDOM) {
            active.push([add, top]);
            top.appendChild(markDOM.dom);
            top = markDOM.contentDOM || markDOM.dom;
          }
        }
      }
      top.appendChild(this.serializeNodeInner(node2, options));
    });
    return target;
  }
  /**
  @internal
  */
  serializeNodeInner(node2, options) {
    if (node2.isText)
      return doc(options).createTextNode(node2.text);
    let { dom, contentDOM } = renderSpec(doc(options), this.nodes[node2.type.name](node2), null, node2.attrs);
    if (contentDOM) {
      if (node2.isLeaf)
        throw new RangeError("Content hole not allowed in a leaf node spec");
      this.serializeFragment(node2.content, options, contentDOM);
    }
    return dom;
  }
  /**
  Serialize this node to a DOM node. This can be useful when you
  need to serialize a part of a document, as opposed to the whole
  document. To serialize a whole document, use
  [`serializeFragment`](https://prosemirror.net/docs/ref/#model.DOMSerializer.serializeFragment) on
  its [content](https://prosemirror.net/docs/ref/#model.Node.content).
  */
  serializeNode(node2, options = {}) {
    let dom = this.serializeNodeInner(node2, options);
    for (let i2 = node2.marks.length - 1; i2 >= 0; i2--) {
      let wrap2 = this.serializeMark(node2.marks[i2], node2.isInline, options);
      if (wrap2) {
        (wrap2.contentDOM || wrap2.dom).appendChild(dom);
        dom = wrap2.dom;
      }
    }
    return dom;
  }
  /**
  @internal
  */
  serializeMark(mark, inline, options = {}) {
    let toDOM = this.marks[mark.type.name];
    return toDOM && renderSpec(doc(options), toDOM(mark, inline), null, mark.attrs);
  }
  static renderSpec(doc3, structure, xmlNS = null, blockArraysIn) {
    if (typeof structure == "string")
      return { dom: doc3.createTextNode(structure) };
    return renderSpec(doc3, structure, xmlNS, blockArraysIn);
  }
  /**
  Build a serializer using the [`toDOM`](https://prosemirror.net/docs/ref/#model.NodeSpec.toDOM)
  properties in a schema's node and mark specs.
  */
  static fromSchema(schema2) {
    return schema2.cached.domSerializer || (schema2.cached.domSerializer = new _DOMSerializer(this.nodesFromSchema(schema2), this.marksFromSchema(schema2)));
  }
  /**
  Gather the serializers in a schema's node specs into an object.
  This can be useful as a base to build a custom serializer from.
  */
  static nodesFromSchema(schema2) {
    let result = gatherToDOM(schema2.nodes);
    if (!result.text)
      result.text = (node2) => node2.text;
    return result;
  }
  /**
  Gather the serializers in a schema's mark specs into an object.
  */
  static marksFromSchema(schema2) {
    return gatherToDOM(schema2.marks);
  }
};
function gatherToDOM(obj) {
  let result = {};
  for (let name in obj) {
    let toDOM = obj[name].spec.toDOM;
    if (toDOM)
      result[name] = toDOM;
  }
  return result;
}
function doc(options) {
  return options.document || window.document;
}
var suspiciousAttributeCache = /* @__PURE__ */ new WeakMap();
function suspiciousAttributes(attrs) {
  let value = suspiciousAttributeCache.get(attrs);
  if (value === void 0)
    suspiciousAttributeCache.set(attrs, value = suspiciousAttributesInner(attrs));
  return value;
}
function suspiciousAttributesInner(attrs) {
  let result = null;
  function scan(value) {
    if (value && typeof value == "object") {
      if (Array.isArray(value)) {
        if (typeof value[0] == "string") {
          if (!result)
            result = [];
          result.push(value);
        } else {
          for (let i2 = 0; i2 < value.length; i2++)
            scan(value[i2]);
        }
      } else {
        for (let prop in value)
          scan(value[prop]);
      }
    }
  }
  scan(attrs);
  return result;
}
function renderSpec(doc3, structure, xmlNS, blockArraysIn) {
  if (structure.nodeType == 1)
    return { dom: structure };
  if (structure.dom && structure.dom.nodeType == 1)
    return structure;
  let tagName = structure[0], suspicious;
  if (typeof tagName != "string")
    throw new RangeError("Invalid array passed to renderSpec");
  if (blockArraysIn && (suspicious = suspiciousAttributes(blockArraysIn)) && suspicious.indexOf(structure) > -1)
    throw new RangeError("Using an array from an attribute object as a DOM spec. This may be an attempted cross site scripting attack.");
  let space = tagName.indexOf(" ");
  if (space > 0) {
    xmlNS = tagName.slice(0, space);
    tagName = tagName.slice(space + 1);
  }
  let contentDOM;
  let dom = xmlNS ? doc3.createElementNS(xmlNS, tagName) : doc3.createElement(tagName);
  let attrs = structure[1], start = 1;
  if (attrs && typeof attrs == "object" && attrs.nodeType == null && !Array.isArray(attrs)) {
    start = 2;
    for (let name in attrs)
      if (attrs[name] != null) {
        let space2 = name.indexOf(" ");
        if (space2 > 0)
          dom.setAttributeNS(name.slice(0, space2), name.slice(space2 + 1), attrs[name]);
        else if (name == "style" && dom.style)
          dom.style.cssText = attrs[name];
        else
          dom.setAttribute(name, attrs[name]);
      }
  }
  for (let i2 = start; i2 < structure.length; i2++) {
    let child = structure[i2];
    if (child === 0) {
      if (i2 < structure.length - 1 || i2 > start)
        throw new RangeError("Content hole must be the only child of its parent node");
      return { dom, contentDOM: dom };
    } else if (typeof child == "string") {
      dom.appendChild(doc3.createTextNode(child));
    } else {
      let { dom: inner, contentDOM: innerContent } = renderSpec(doc3, child, xmlNS, blockArraysIn);
      dom.appendChild(inner);
      if (innerContent) {
        if (contentDOM)
          throw new RangeError("Multiple content holes");
        contentDOM = innerContent;
      }
    }
  }
  return { dom, contentDOM };
}

// node_modules/.pnpm/prosemirror-transform@1.12.4/node_modules/prosemirror-transform/dist/index.js
var lower16 = 65535;
var factor16 = Math.pow(2, 16);
function makeRecover(index2, offset) {
  return index2 + offset * factor16;
}
function recoverIndex(value) {
  return value & lower16;
}
function recoverOffset(value) {
  return (value - (value & lower16)) / factor16;
}
var DEL_BEFORE = 1;
var DEL_AFTER = 2;
var DEL_ACROSS = 4;
var DEL_SIDE = 8;
var MapResult = class {
  /**
  @internal
  */
  constructor(pos, delInfo, recover) {
    this.pos = pos;
    this.delInfo = delInfo;
    this.recover = recover;
  }
  /**
  Tells you whether the position was deleted, that is, whether the
  step removed the token on the side queried (via the `assoc`)
  argument from the document.
  */
  get deleted() {
    return (this.delInfo & DEL_SIDE) > 0;
  }
  /**
  Tells you whether the token before the mapped position was deleted.
  */
  get deletedBefore() {
    return (this.delInfo & (DEL_BEFORE | DEL_ACROSS)) > 0;
  }
  /**
  True when the token after the mapped position was deleted.
  */
  get deletedAfter() {
    return (this.delInfo & (DEL_AFTER | DEL_ACROSS)) > 0;
  }
  /**
  Tells whether any of the steps mapped through deletes across the
  position (including both the token before and after the
  position).
  */
  get deletedAcross() {
    return (this.delInfo & DEL_ACROSS) > 0;
  }
};
var StepMap = class _StepMap {
  /**
  Create a position map. The modifications to the document are
  represented as an array of numbers, in which each group of three
  represents a modified chunk as `[start, oldSize, newSize]`.
  */
  constructor(ranges, inverted = false) {
    this.ranges = ranges;
    this.inverted = inverted;
    if (!ranges.length && _StepMap.empty)
      return _StepMap.empty;
  }
  /**
  @internal
  */
  recover(value) {
    let diff = 0, index2 = recoverIndex(value);
    if (!this.inverted)
      for (let i2 = 0; i2 < index2; i2++)
        diff += this.ranges[i2 * 3 + 2] - this.ranges[i2 * 3 + 1];
    return this.ranges[index2 * 3] + diff + recoverOffset(value);
  }
  mapResult(pos, assoc = 1) {
    return this._map(pos, assoc, false);
  }
  map(pos, assoc = 1) {
    return this._map(pos, assoc, true);
  }
  /**
  @internal
  */
  _map(pos, assoc, simple) {
    let diff = 0, oldIndex = this.inverted ? 2 : 1, newIndex = this.inverted ? 1 : 2;
    for (let i2 = 0; i2 < this.ranges.length; i2 += 3) {
      let start = this.ranges[i2] - (this.inverted ? diff : 0);
      if (start > pos)
        break;
      let oldSize = this.ranges[i2 + oldIndex], newSize = this.ranges[i2 + newIndex], end = start + oldSize;
      if (pos <= end) {
        let side = !oldSize ? assoc : pos == start ? -1 : pos == end ? 1 : assoc;
        let result = start + diff + (side < 0 ? 0 : newSize);
        if (simple)
          return result;
        let recover = pos == (assoc < 0 ? start : end) ? null : makeRecover(i2 / 3, pos - start);
        let del2 = 0;
        if (oldSize) {
          del2 |= pos == start ? DEL_AFTER : pos == end ? DEL_BEFORE : DEL_ACROSS;
          if (assoc < 0 ? pos != start : pos != end)
            del2 |= DEL_SIDE;
        }
        return new MapResult(result, del2, recover);
      }
      diff += newSize - oldSize;
    }
    return simple ? pos + diff : new MapResult(pos + diff, 0, null);
  }
  /**
  @internal
  */
  touches(pos, recover) {
    let diff = 0, index2 = recoverIndex(recover);
    let oldIndex = this.inverted ? 2 : 1, newIndex = this.inverted ? 1 : 2;
    for (let i2 = 0; i2 < this.ranges.length; i2 += 3) {
      let start = this.ranges[i2] - (this.inverted ? diff : 0);
      if (start > pos)
        break;
      let oldSize = this.ranges[i2 + oldIndex], end = start + oldSize;
      if (pos <= end && i2 == index2 * 3)
        return true;
      diff += this.ranges[i2 + newIndex] - oldSize;
    }
    return false;
  }
  /**
  Calls the given function on each of the changed ranges included in
  this map.
  */
  forEach(f) {
    let oldIndex = this.inverted ? 2 : 1, newIndex = this.inverted ? 1 : 2;
    for (let i2 = 0, diff = 0; i2 < this.ranges.length; i2 += 3) {
      let start = this.ranges[i2], oldStart = start - (this.inverted ? diff : 0), newStart = start + (this.inverted ? 0 : diff);
      let oldSize = this.ranges[i2 + oldIndex], newSize = this.ranges[i2 + newIndex];
      f(oldStart, oldStart + oldSize, newStart, newStart + newSize);
      diff += newSize - oldSize;
    }
  }
  /**
  Create an inverted version of this map. The result can be used to
  map positions in the post-step document to the pre-step document.
  */
  invert() {
    return new _StepMap(this.ranges, !this.inverted);
  }
  /**
  @internal
  */
  toString() {
    return (this.inverted ? "-" : "") + JSON.stringify(this.ranges);
  }
  /**
  Create a map that moves all positions by offset `n` (which may be
  negative). This can be useful when applying steps meant for a
  sub-document to a larger document, or vice-versa.
  */
  static offset(n) {
    return n == 0 ? _StepMap.empty : new _StepMap(n < 0 ? [0, -n, 0] : [0, 0, n]);
  }
};
StepMap.empty = new StepMap([]);
var Mapping = class _Mapping {
  /**
  Create a new mapping with the given position maps.
  */
  constructor(maps, mirror, from2 = 0, to = maps ? maps.length : 0) {
    this.mirror = mirror;
    this.from = from2;
    this.to = to;
    this._maps = maps || [];
    this.ownData = !(maps || mirror);
  }
  /**
  The step maps in this mapping.
  */
  get maps() {
    return this._maps;
  }
  /**
  Create a mapping that maps only through a part of this one.
  */
  slice(from2 = 0, to = this.maps.length) {
    return new _Mapping(this._maps, this.mirror, from2, to);
  }
  /**
  Add a step map to the end of this mapping. If `mirrors` is
  given, it should be the index of the step map that is the mirror
  image of this one.
  */
  appendMap(map5, mirrors) {
    if (!this.ownData) {
      this._maps = this._maps.slice();
      this.mirror = this.mirror && this.mirror.slice();
      this.ownData = true;
    }
    this.to = this._maps.push(map5);
    if (mirrors != null)
      this.setMirror(this._maps.length - 1, mirrors);
  }
  /**
  Add all the step maps in a given mapping to this one (preserving
  mirroring information).
  */
  appendMapping(mapping) {
    for (let i2 = 0, startSize = this._maps.length; i2 < mapping._maps.length; i2++) {
      let mirr = mapping.getMirror(i2);
      this.appendMap(mapping._maps[i2], mirr != null && mirr < i2 ? startSize + mirr : void 0);
    }
  }
  /**
  Finds the offset of the step map that mirrors the map at the
  given offset, in this mapping (as per the second argument to
  `appendMap`).
  */
  getMirror(n) {
    if (this.mirror) {
      for (let i2 = 0; i2 < this.mirror.length; i2++)
        if (this.mirror[i2] == n)
          return this.mirror[i2 + (i2 % 2 ? -1 : 1)];
    }
  }
  /**
  @internal
  */
  setMirror(n, m) {
    if (!this.mirror)
      this.mirror = [];
    this.mirror.push(n, m);
  }
  /**
  Append the inverse of the given mapping to this one.
  */
  appendMappingInverted(mapping) {
    for (let i2 = mapping.maps.length - 1, totalSize = this._maps.length + mapping._maps.length; i2 >= 0; i2--) {
      let mirr = mapping.getMirror(i2);
      this.appendMap(mapping._maps[i2].invert(), mirr != null && mirr > i2 ? totalSize - mirr - 1 : void 0);
    }
  }
  /**
  Create an inverted version of this mapping.
  */
  invert() {
    let inverse = new _Mapping();
    inverse.appendMappingInverted(this);
    return inverse;
  }
  /**
  Map a position through this mapping.
  */
  map(pos, assoc = 1) {
    if (this.mirror)
      return this._map(pos, assoc, true);
    for (let i2 = this.from; i2 < this.to; i2++)
      pos = this._maps[i2].map(pos, assoc);
    return pos;
  }
  /**
  Map a position through this mapping, returning a mapping
  result.
  */
  mapResult(pos, assoc = 1) {
    return this._map(pos, assoc, false);
  }
  /**
  @internal
  */
  _map(pos, assoc, simple) {
    let delInfo = 0;
    for (let i2 = this.from; i2 < this.to; i2++) {
      let map5 = this._maps[i2], result = map5.mapResult(pos, assoc);
      if (result.recover != null) {
        let corr = this.getMirror(i2);
        if (corr != null && corr > i2 && corr < this.to) {
          i2 = corr;
          pos = this._maps[corr].recover(result.recover);
          continue;
        }
      }
      delInfo |= result.delInfo;
      pos = result.pos;
    }
    return simple ? pos : new MapResult(pos, delInfo, null);
  }
};
var stepsByID = /* @__PURE__ */ Object.create(null);
var Step = class {
  /**
  Get the step map that represents the changes made by this step,
  and which can be used to transform between positions in the old
  and the new document.
  */
  getMap() {
    return StepMap.empty;
  }
  /**
  Try to merge this step with another one, to be applied directly
  after it. Returns the merged step when possible, null if the
  steps can't be merged.
  */
  merge(other) {
    return null;
  }
  /**
  Deserialize a step from its JSON representation. Will call
  through to the step class' own implementation of this method.
  */
  static fromJSON(schema2, json) {
    if (!json || !json.stepType)
      throw new RangeError("Invalid input for Step.fromJSON");
    let type = stepsByID[json.stepType];
    if (!type)
      throw new RangeError(`No step type ${json.stepType} defined`);
    return type.fromJSON(schema2, json);
  }
  /**
  To be able to serialize steps to JSON, each step needs a string
  ID to attach to its JSON representation. Use this method to
  register an ID for your step classes. Try to pick something
  that's unlikely to clash with steps from other modules.
  */
  static jsonID(id, stepClass) {
    if (id in stepsByID)
      throw new RangeError("Duplicate use of step JSON ID " + id);
    stepsByID[id] = stepClass;
    stepClass.prototype.jsonID = id;
    return stepClass;
  }
};
var StepResult = class _StepResult {
  /**
  @internal
  */
  constructor(doc3, failed) {
    this.doc = doc3;
    this.failed = failed;
  }
  /**
  Create a successful step result.
  */
  static ok(doc3) {
    return new _StepResult(doc3, null);
  }
  /**
  Create a failed step result.
  */
  static fail(message) {
    return new _StepResult(null, message);
  }
  /**
  Call [`Node.replace`](https://prosemirror.net/docs/ref/#model.Node.replace) with the given
  arguments. Create a successful result if it succeeds, and a
  failed one if it throws a `ReplaceError`.
  */
  static fromReplace(doc3, from2, to, slice2) {
    try {
      return _StepResult.ok(doc3.replace(from2, to, slice2));
    } catch (e) {
      if (e instanceof ReplaceError)
        return _StepResult.fail(e.message);
      throw e;
    }
  }
};
function mapFragment(fragment, f, parent) {
  let mapped = [];
  for (let i2 = 0; i2 < fragment.childCount; i2++) {
    let child = fragment.child(i2);
    if (child.content.size)
      child = child.copy(mapFragment(child.content, f, child));
    if (child.isInline)
      child = f(child, parent, i2);
    mapped.push(child);
  }
  return Fragment.fromArray(mapped);
}
var AddMarkStep = class _AddMarkStep extends Step {
  /**
  Create a mark step.
  */
  constructor(from2, to, mark) {
    super();
    this.from = from2;
    this.to = to;
    this.mark = mark;
  }
  apply(doc3) {
    let oldSlice = doc3.slice(this.from, this.to), $from = doc3.resolve(this.from);
    let parent = $from.node($from.sharedDepth(this.to));
    let slice2 = new Slice(mapFragment(oldSlice.content, (node2, parent2) => {
      if (!node2.isAtom || !parent2.type.allowsMarkType(this.mark.type))
        return node2;
      return node2.mark(this.mark.addToSet(node2.marks));
    }, parent), oldSlice.openStart, oldSlice.openEnd);
    return StepResult.fromReplace(doc3, this.from, this.to, slice2);
  }
  invert(doc3) {
    let steps = [];
    doc3.nodesBetween(this.from, this.to, (node2, pos) => {
      if (node2.isInline && node2.isAtom) {
        let added = this.mark.addToSet(node2.marks);
        if (!Mark.sameSet(added, node2.marks)) {
          let from2 = Math.max(this.from, pos), to = Math.min(this.to, pos + node2.nodeSize);
          pushMarkStep(RemoveMarkStep, from2, to, this.mark, steps);
          for (let mark of node2.marks)
            if (!mark.isInSet(added))
              pushMarkStep(_AddMarkStep, from2, to, mark, steps);
        }
      }
    });
    return steps.length == 1 ? steps[0] : new MarkSetStep(steps);
  }
  map(mapping) {
    let from2 = mapping.map(this.from, 1), to = mapping.map(this.to, -1);
    if (from2 >= to)
      return null;
    return new _AddMarkStep(from2, to, this.mark);
  }
  merge(other) {
    if (other instanceof _AddMarkStep && other.mark.eq(this.mark) && this.from <= other.to && this.to >= other.from)
      return new _AddMarkStep(Math.min(this.from, other.from), Math.max(this.to, other.to), this.mark);
    return null;
  }
  toJSON() {
    return {
      stepType: "addMark",
      mark: this.mark.toJSON(),
      from: this.from,
      to: this.to
    };
  }
  /**
  @internal
  */
  static fromJSON(schema2, json) {
    if (typeof json.from != "number" || typeof json.to != "number")
      throw new RangeError("Invalid input for AddMarkStep.fromJSON");
    return new _AddMarkStep(json.from, json.to, schema2.markFromJSON(json.mark));
  }
};
Step.jsonID("addMark", AddMarkStep);
var RemoveMarkStep = class _RemoveMarkStep extends Step {
  /**
  Create a mark-removing step.
  */
  constructor(from2, to, mark) {
    super();
    this.from = from2;
    this.to = to;
    this.mark = mark;
  }
  apply(doc3) {
    let oldSlice = doc3.slice(this.from, this.to);
    let slice2 = new Slice(mapFragment(oldSlice.content, (node2) => {
      return node2.mark(this.mark.removeFromSet(node2.marks));
    }, doc3), oldSlice.openStart, oldSlice.openEnd);
    return StepResult.fromReplace(doc3, this.from, this.to, slice2);
  }
  invert(doc3) {
    let steps = [];
    doc3.nodesBetween(this.from, this.to, (node2, pos) => {
      if (node2.isInline && node2.isAtom && this.mark.isInSet(node2.marks))
        pushMarkStep(AddMarkStep, Math.max(this.from, pos), Math.min(this.to, pos + node2.nodeSize), this.mark, steps);
    });
    return steps.length == 1 ? steps[0] : new MarkSetStep(steps);
  }
  map(mapping) {
    let from2 = mapping.map(this.from, 1), to = mapping.map(this.to, -1);
    if (from2 >= to)
      return null;
    return new _RemoveMarkStep(from2, to, this.mark);
  }
  merge(other) {
    if (other instanceof _RemoveMarkStep && other.mark.eq(this.mark) && this.from <= other.to && this.to >= other.from)
      return new _RemoveMarkStep(Math.min(this.from, other.from), Math.max(this.to, other.to), this.mark);
    return null;
  }
  toJSON() {
    return {
      stepType: "removeMark",
      mark: this.mark.toJSON(),
      from: this.from,
      to: this.to
    };
  }
  /**
  @internal
  */
  static fromJSON(schema2, json) {
    if (typeof json.from != "number" || typeof json.to != "number")
      throw new RangeError("Invalid input for RemoveMarkStep.fromJSON");
    return new _RemoveMarkStep(json.from, json.to, schema2.markFromJSON(json.mark));
  }
};
Step.jsonID("removeMark", RemoveMarkStep);
function pushMarkStep(cls, from2, to, mark, target) {
  let last = target.length ? target[target.length - 1] : null;
  if (last && last instanceof cls && last.to == from2 && last.mark.eq(mark)) {
    target[target.length - 1] = new cls(last.from, to, mark);
  } else {
    target.push(new cls(from2, to, mark));
  }
}
var MarkSetStep = class _MarkSetStep extends Step {
  constructor(steps) {
    super();
    this.steps = steps;
  }
  apply(doc3) {
    for (let step of this.steps) {
      let result = step.apply(doc3);
      if (!result.doc)
        return result;
      doc3 = result.doc;
    }
    return new StepResult(doc3, null);
  }
  invert(doc3) {
    return new _MarkSetStep(this.steps.map((s) => s.invert(doc3)));
  }
  map(mapping) {
    let result = [];
    for (let step of this.steps) {
      let mapped = step.map(mapping);
      if (mapped)
        result.push(mapped);
    }
    return result.length ? new _MarkSetStep(result) : null;
  }
  toJSON() {
    return { stepType: "markSet", steps: this.steps.map((s) => s.toJSON()) };
  }
  static fromJSON(schema2, json) {
    if (!Array.isArray(json.steps) || !json.steps.every((s) => s.stepType == "addMark" || s.stepType == "removeMark"))
      throw new RangeError("Invalid JSON for MarkSetStep");
    return new _MarkSetStep(json.steps.map((s) => Step.fromJSON(schema2, s)));
  }
};
Step.jsonID("markSet", MarkSetStep);
var AddNodeMarkStep = class _AddNodeMarkStep extends Step {
  /**
  Create a node mark step.
  */
  constructor(pos, mark) {
    super();
    this.pos = pos;
    this.mark = mark;
  }
  apply(doc3) {
    let node2 = doc3.nodeAt(this.pos);
    if (!node2)
      return StepResult.fail("No node at mark step's position");
    let updated = node2.type.create(node2.attrs, null, this.mark.addToSet(node2.marks));
    return StepResult.fromReplace(doc3, this.pos, this.pos + 1, new Slice(Fragment.from(updated), 0, node2.isLeaf ? 0 : 1));
  }
  invert(doc3) {
    let node2 = doc3.nodeAt(this.pos);
    if (node2) {
      let newSet = this.mark.addToSet(node2.marks);
      if (newSet.length == node2.marks.length) {
        for (let i2 = 0; i2 < node2.marks.length; i2++)
          if (!node2.marks[i2].isInSet(newSet))
            return new _AddNodeMarkStep(this.pos, node2.marks[i2]);
        return new _AddNodeMarkStep(this.pos, this.mark);
      }
    }
    return new RemoveNodeMarkStep(this.pos, this.mark);
  }
  map(mapping) {
    let pos = mapping.mapResult(this.pos, 1);
    return pos.deletedAfter ? null : new _AddNodeMarkStep(pos.pos, this.mark);
  }
  toJSON() {
    return { stepType: "addNodeMark", pos: this.pos, mark: this.mark.toJSON() };
  }
  /**
  @internal
  */
  static fromJSON(schema2, json) {
    if (typeof json.pos != "number")
      throw new RangeError("Invalid input for AddNodeMarkStep.fromJSON");
    return new _AddNodeMarkStep(json.pos, schema2.markFromJSON(json.mark));
  }
};
Step.jsonID("addNodeMark", AddNodeMarkStep);
var RemoveNodeMarkStep = class _RemoveNodeMarkStep extends Step {
  /**
  Create a mark-removing step.
  */
  constructor(pos, mark) {
    super();
    this.pos = pos;
    this.mark = mark;
  }
  apply(doc3) {
    let node2 = doc3.nodeAt(this.pos);
    if (!node2)
      return StepResult.fail("No node at mark step's position");
    let updated = node2.type.create(node2.attrs, null, this.mark.removeFromSet(node2.marks));
    return StepResult.fromReplace(doc3, this.pos, this.pos + 1, new Slice(Fragment.from(updated), 0, node2.isLeaf ? 0 : 1));
  }
  invert(doc3) {
    let node2 = doc3.nodeAt(this.pos);
    if (!node2 || !this.mark.isInSet(node2.marks))
      return this;
    return new AddNodeMarkStep(this.pos, this.mark);
  }
  map(mapping) {
    let pos = mapping.mapResult(this.pos, 1);
    return pos.deletedAfter ? null : new _RemoveNodeMarkStep(pos.pos, this.mark);
  }
  toJSON() {
    return { stepType: "removeNodeMark", pos: this.pos, mark: this.mark.toJSON() };
  }
  /**
  @internal
  */
  static fromJSON(schema2, json) {
    if (typeof json.pos != "number")
      throw new RangeError("Invalid input for RemoveNodeMarkStep.fromJSON");
    return new _RemoveNodeMarkStep(json.pos, schema2.markFromJSON(json.mark));
  }
};
Step.jsonID("removeNodeMark", RemoveNodeMarkStep);
var ReplaceStep = class _ReplaceStep extends Step {
  /**
  The given `slice` should fit the 'gap' between `from` and
  `to`—the depths must line up, and the surrounding nodes must be
  able to be joined with the open sides of the slice. When
  `structure` is true, the step will fail if the content between
  from and to is not just a sequence of closing and then opening
  tokens (this is to guard against rebased replace steps
  overwriting something they weren't supposed to).
  */
  constructor(from2, to, slice2, structure = false) {
    super();
    this.from = from2;
    this.to = to;
    this.slice = slice2;
    this.structure = structure;
  }
  apply(doc3) {
    if (this.structure && contentBetween(doc3, this.from, this.to))
      return StepResult.fail("Structure replace would overwrite content");
    return StepResult.fromReplace(doc3, this.from, this.to, this.slice);
  }
  getMap() {
    return new StepMap([this.from, this.to - this.from, this.slice.size]);
  }
  invert(doc3) {
    return new _ReplaceStep(this.from, this.from + this.slice.size, doc3.slice(this.from, this.to));
  }
  map(mapping) {
    let to = mapping.mapResult(this.to, -1);
    let from2 = this.from == this.to && _ReplaceStep.MAP_BIAS < 0 ? to : mapping.mapResult(this.from, 1);
    if (from2.deletedAcross && to.deletedAcross)
      return null;
    return new _ReplaceStep(from2.pos, Math.max(from2.pos, to.pos), this.slice, this.structure);
  }
  merge(other) {
    if (!(other instanceof _ReplaceStep) || other.structure || this.structure)
      return null;
    if (this.from + this.slice.size == other.from && !this.slice.openEnd && !other.slice.openStart) {
      let slice2 = this.slice.size + other.slice.size == 0 ? Slice.empty : new Slice(this.slice.content.append(other.slice.content), this.slice.openStart, other.slice.openEnd);
      return new _ReplaceStep(this.from, this.to + (other.to - other.from), slice2, this.structure);
    } else if (other.to == this.from && !this.slice.openStart && !other.slice.openEnd) {
      let slice2 = this.slice.size + other.slice.size == 0 ? Slice.empty : new Slice(other.slice.content.append(this.slice.content), other.slice.openStart, this.slice.openEnd);
      return new _ReplaceStep(other.from, this.to, slice2, this.structure);
    } else {
      return null;
    }
  }
  toJSON() {
    let json = { stepType: "replace", from: this.from, to: this.to };
    if (this.slice.size)
      json.slice = this.slice.toJSON();
    if (this.structure)
      json.structure = true;
    return json;
  }
  /**
  @internal
  */
  static fromJSON(schema2, json) {
    if (typeof json.from != "number" || typeof json.to != "number")
      throw new RangeError("Invalid input for ReplaceStep.fromJSON");
    return new _ReplaceStep(json.from, json.to, Slice.fromJSON(schema2, json.slice), !!json.structure);
  }
};
ReplaceStep.MAP_BIAS = 1;
Step.jsonID("replace", ReplaceStep);
var ReplaceAroundStep = class _ReplaceAroundStep extends Step {
  /**
  Create a replace-around step with the given range and gap.
  `insert` should be the point in the slice into which the content
  of the gap should be moved. `structure` has the same meaning as
  it has in the [`ReplaceStep`](https://prosemirror.net/docs/ref/#transform.ReplaceStep) class.
  */
  constructor(from2, to, gapFrom, gapTo, slice2, insert, structure = false) {
    super();
    this.from = from2;
    this.to = to;
    this.gapFrom = gapFrom;
    this.gapTo = gapTo;
    this.slice = slice2;
    this.insert = insert;
    this.structure = structure;
  }
  apply(doc3) {
    if (this.structure && (contentBetween(doc3, this.from, this.gapFrom) || contentBetween(doc3, this.gapTo, this.to)))
      return StepResult.fail("Structure gap-replace would overwrite content");
    let gap = doc3.slice(this.gapFrom, this.gapTo);
    if (gap.openStart || gap.openEnd)
      return StepResult.fail("Gap is not a flat range");
    let inserted = this.slice.insertAt(this.insert, gap.content);
    if (!inserted)
      return StepResult.fail("Content does not fit in gap");
    return StepResult.fromReplace(doc3, this.from, this.to, inserted);
  }
  getMap() {
    return new StepMap([
      this.from,
      this.gapFrom - this.from,
      this.insert,
      this.gapTo,
      this.to - this.gapTo,
      this.slice.size - this.insert
    ]);
  }
  invert(doc3) {
    let gap = this.gapTo - this.gapFrom;
    return new _ReplaceAroundStep(this.from, this.from + this.slice.size + gap, this.from + this.insert, this.from + this.insert + gap, doc3.slice(this.from, this.to).removeBetween(this.gapFrom - this.from, this.gapTo - this.from), this.gapFrom - this.from, this.structure);
  }
  map(mapping) {
    let from2 = mapping.mapResult(this.from, 1), to = mapping.mapResult(this.to, -1);
    let gapFrom = this.from == this.gapFrom ? from2.pos : mapping.map(this.gapFrom, -1);
    let gapTo = this.to == this.gapTo ? to.pos : mapping.map(this.gapTo, 1);
    if (from2.deletedAcross && to.deletedAcross || gapFrom < from2.pos || gapTo > to.pos)
      return null;
    return new _ReplaceAroundStep(from2.pos, to.pos, gapFrom, gapTo, this.slice, this.insert, this.structure);
  }
  toJSON() {
    let json = {
      stepType: "replaceAround",
      from: this.from,
      to: this.to,
      gapFrom: this.gapFrom,
      gapTo: this.gapTo,
      insert: this.insert
    };
    if (this.slice.size)
      json.slice = this.slice.toJSON();
    if (this.structure)
      json.structure = true;
    return json;
  }
  /**
  @internal
  */
  static fromJSON(schema2, json) {
    if (typeof json.from != "number" || typeof json.to != "number" || typeof json.gapFrom != "number" || typeof json.gapTo != "number" || typeof json.insert != "number")
      throw new RangeError("Invalid input for ReplaceAroundStep.fromJSON");
    return new _ReplaceAroundStep(json.from, json.to, json.gapFrom, json.gapTo, Slice.fromJSON(schema2, json.slice), json.insert, !!json.structure);
  }
};
Step.jsonID("replaceAround", ReplaceAroundStep);
function contentBetween(doc3, from2, to) {
  let $from = doc3.resolve(from2), dist = to - from2, depth = $from.depth;
  while (dist > 0 && depth > 0 && $from.indexAfter(depth) == $from.node(depth).childCount) {
    depth--;
    dist--;
  }
  if (dist > 0) {
    let next = $from.node(depth).maybeChild($from.indexAfter(depth));
    while (dist > 0) {
      if (!next || next.isLeaf)
        return true;
      next = next.firstChild;
      dist--;
    }
  }
  return false;
}
function addMark(tr, from2, to, mark) {
  let added = [];
  tr.doc.nodesBetween(from2, to, (node2, pos, parent) => {
    if (!node2.isInline)
      return;
    let marks = node2.marks;
    if (!mark.isInSet(marks) && parent.type.allowsMarkType(mark.type)) {
      let start = Math.max(pos, from2), end = Math.min(pos + node2.nodeSize, to);
      pushMarkStep(AddMarkStep, start, end, mark, added);
    }
  });
  added.forEach((s) => tr.step(s));
}
function removeMark(tr, from2, to, mark) {
  let matched = [], step = 0;
  tr.doc.nodesBetween(from2, to, (node2, pos) => {
    if (!node2.isInline || !node2.isAtom)
      return;
    step++;
    let toRemove = null;
    if (mark instanceof MarkType) {
      let set = node2.marks, found2;
      while (found2 = mark.isInSet(set)) {
        (toRemove || (toRemove = [])).push(found2);
        set = found2.removeFromSet(set);
      }
    } else if (mark) {
      if (mark.isInSet(node2.marks))
        toRemove = [mark];
    } else {
      toRemove = node2.marks;
    }
    if (toRemove && toRemove.length) {
      let end = Math.min(pos + node2.nodeSize, to);
      for (let i2 = 0; i2 < toRemove.length; i2++) {
        let style = toRemove[i2], found2;
        for (let j = 0; j < matched.length; j++) {
          let m = matched[j];
          if (m.step == step - 1 && style.eq(matched[j].style))
            found2 = m;
        }
        if (found2) {
          found2.to = end;
          found2.step = step;
        } else {
          matched.push({ style, from: Math.max(pos, from2), to: end, step });
        }
      }
    }
  });
  matched.forEach((m) => tr.step(new RemoveMarkStep(m.from, m.to, m.style)));
}
function clearIncompatible(tr, pos, parentType, match = parentType.contentMatch, clearNewlines = true) {
  let node2 = tr.doc.nodeAt(pos);
  let replSteps = [], cur = pos + 1;
  for (let i2 = 0; i2 < node2.childCount; i2++) {
    let child = node2.child(i2), end = cur + child.nodeSize;
    let allowed = match.matchType(child.type);
    if (!allowed) {
      replSteps.push(new ReplaceStep(cur, end, Slice.empty));
    } else {
      match = allowed;
      for (let j = 0; j < child.marks.length; j++)
        if (!parentType.allowsMarkType(child.marks[j].type))
          tr.step(new RemoveMarkStep(cur, end, child.marks[j]));
      if (clearNewlines && child.isText && parentType.whitespace != "pre") {
        let m, newline = /\r?\n|\r/g, slice2;
        while (m = newline.exec(child.text)) {
          if (!slice2)
            slice2 = new Slice(Fragment.from(parentType.schema.text(" ", parentType.allowedMarks(child.marks))), 0, 0);
          replSteps.push(new ReplaceStep(cur + m.index, cur + m.index + m[0].length, slice2));
        }
      }
    }
    cur = end;
  }
  if (!match.validEnd) {
    let fill = match.fillBefore(Fragment.empty, true);
    tr.replace(cur, cur, new Slice(fill, 0, 0));
  }
  for (let i2 = replSteps.length - 1; i2 >= 0; i2--)
    tr.step(replSteps[i2]);
}
function canCut(node2, start, end) {
  return (start == 0 || node2.canReplace(start, node2.childCount)) && (end == node2.childCount || node2.canReplace(0, end));
}
function liftTarget(range) {
  let parent = range.parent;
  let content3 = parent.content.cutByIndex(range.startIndex, range.endIndex);
  for (let depth = range.depth, contentBefore = 0, contentAfter = 0; ; --depth) {
    let node2 = range.$from.node(depth);
    let index2 = range.$from.index(depth) + contentBefore, endIndex = range.$to.indexAfter(depth) - contentAfter;
    if (depth < range.depth && node2.canReplace(index2, endIndex, content3))
      return depth;
    if (depth == 0 || node2.type.spec.isolating || !canCut(node2, index2, endIndex))
      break;
    if (index2)
      contentBefore = 1;
    if (endIndex < node2.childCount)
      contentAfter = 1;
  }
  return null;
}
function lift(tr, range, target) {
  let { $from, $to, depth } = range;
  let gapStart = $from.before(depth + 1), gapEnd = $to.after(depth + 1);
  let start = gapStart, end = gapEnd;
  let before = Fragment.empty, openStart = 0;
  for (let d = depth, splitting = false; d > target; d--)
    if (splitting || $from.index(d) > 0) {
      splitting = true;
      before = Fragment.from($from.node(d).copy(before));
      openStart++;
    } else {
      start--;
    }
  let after = Fragment.empty, openEnd = 0;
  for (let d = depth, splitting = false; d > target; d--)
    if (splitting || $to.after(d + 1) < $to.end(d)) {
      splitting = true;
      after = Fragment.from($to.node(d).copy(after));
      openEnd++;
    } else {
      end++;
    }
  tr.step(new ReplaceAroundStep(start, end, gapStart, gapEnd, new Slice(before.append(after), openStart, openEnd), before.size - openStart, true));
}
function wrap(tr, range, wrappers) {
  let content3 = Fragment.empty;
  for (let i2 = wrappers.length - 1; i2 >= 0; i2--) {
    if (content3.size) {
      let match = wrappers[i2].type.contentMatch.matchFragment(content3);
      if (!match || !match.validEnd)
        throw new RangeError("Wrapper type given to Transform.wrap does not form valid content of its parent wrapper");
    }
    content3 = Fragment.from(wrappers[i2].type.create(wrappers[i2].attrs, content3));
  }
  let start = range.start, end = range.end;
  tr.step(new ReplaceAroundStep(start, end, start, end, new Slice(content3, 0, 0), wrappers.length, true));
}
function setBlockType(tr, from2, to, type, attrs) {
  if (!type.isTextblock)
    throw new RangeError("Type given to setBlockType should be a textblock");
  let mapFrom = tr.steps.length;
  tr.doc.nodesBetween(from2, to, (node2, pos) => {
    let attrsHere = typeof attrs == "function" ? attrs(node2) : attrs;
    if (node2.isTextblock && !node2.hasMarkup(type, attrsHere) && canChangeType(tr.doc, tr.mapping.slice(mapFrom).map(pos), type)) {
      let convertNewlines = null;
      if (type.schema.linebreakReplacement) {
        let pre = type.whitespace == "pre", supportLinebreak = !!type.contentMatch.matchType(type.schema.linebreakReplacement);
        if (pre && !supportLinebreak)
          convertNewlines = false;
        else if (!pre && supportLinebreak)
          convertNewlines = true;
      }
      if (convertNewlines === false)
        replaceLinebreaks(tr, node2, pos, mapFrom);
      clearIncompatible(tr, tr.mapping.slice(mapFrom).map(pos, 1), type, void 0, convertNewlines === null);
      let mapping = tr.mapping.slice(mapFrom);
      let startM = mapping.map(pos, 1), endM = mapping.map(pos + node2.nodeSize, 1);
      tr.step(new ReplaceAroundStep(startM, endM, startM + 1, endM - 1, new Slice(Fragment.from(type.create(attrsHere, null, node2.marks)), 0, 0), 1, true));
      if (convertNewlines === true)
        replaceNewlines(tr, node2, pos, mapFrom);
      return false;
    }
  });
}
function replaceNewlines(tr, node2, pos, mapFrom) {
  node2.forEach((child, offset) => {
    if (child.isText) {
      let m, newline = /\r?\n|\r/g;
      while (m = newline.exec(child.text)) {
        let start = tr.mapping.slice(mapFrom).map(pos + 1 + offset + m.index);
        tr.replaceWith(start, start + 1, node2.type.schema.linebreakReplacement.create());
      }
    }
  });
}
function replaceLinebreaks(tr, node2, pos, mapFrom) {
  node2.forEach((child, offset) => {
    if (child.type == child.type.schema.linebreakReplacement) {
      let start = tr.mapping.slice(mapFrom).map(pos + 1 + offset);
      tr.replaceWith(start, start + 1, node2.type.schema.text("\n"));
    }
  });
}
function canChangeType(doc3, pos, type) {
  let $pos = doc3.resolve(pos), index2 = $pos.index();
  return $pos.parent.canReplaceWith(index2, index2 + 1, type);
}
function setNodeMarkup(tr, pos, type, attrs, marks) {
  let node2 = tr.doc.nodeAt(pos);
  if (!node2)
    throw new RangeError("No node at given position");
  if (!type)
    type = node2.type;
  let newNode = type.create(attrs, null, marks || node2.marks);
  if (node2.isLeaf)
    return tr.replaceWith(pos, pos + node2.nodeSize, newNode);
  if (!type.validContent(node2.content))
    throw new RangeError("Invalid content for node type " + type.name);
  tr.step(new ReplaceAroundStep(pos, pos + node2.nodeSize, pos + 1, pos + node2.nodeSize - 1, new Slice(Fragment.from(newNode), 0, 0), 1, true));
}
function canSplit(doc3, pos, depth = 1, typesAfter) {
  let $pos = doc3.resolve(pos), base2 = $pos.depth - depth;
  let innerType = typesAfter && typesAfter[typesAfter.length - 1] || $pos.parent;
  if (base2 < 0 || $pos.parent.type.spec.isolating || !$pos.parent.canReplace($pos.index(), $pos.parent.childCount) || !innerType.type.validContent($pos.parent.content.cutByIndex($pos.index(), $pos.parent.childCount)))
    return false;
  for (let d = $pos.depth - 1, i2 = depth - 2; d > base2; d--, i2--) {
    let node2 = $pos.node(d), index3 = $pos.index(d);
    if (node2.type.spec.isolating)
      return false;
    let rest = node2.content.cutByIndex(index3, node2.childCount);
    let overrideChild = typesAfter && typesAfter[i2 + 1];
    if (overrideChild)
      rest = rest.replaceChild(0, overrideChild.type.create(overrideChild.attrs));
    let after = typesAfter && typesAfter[i2] || node2;
    if (!node2.canReplace(index3 + 1, node2.childCount) || !after.type.validContent(rest))
      return false;
  }
  let index2 = $pos.indexAfter(base2);
  let baseType = typesAfter && typesAfter[0];
  return $pos.node(base2).canReplaceWith(index2, index2, baseType ? baseType.type : $pos.node(base2 + 1).type);
}
function split(tr, pos, depth = 1, typesAfter) {
  let $pos = tr.doc.resolve(pos), before = Fragment.empty, after = Fragment.empty;
  for (let d = $pos.depth, e = $pos.depth - depth, i2 = depth - 1; d > e; d--, i2--) {
    before = Fragment.from($pos.node(d).copy(before));
    let typeAfter = typesAfter && typesAfter[i2];
    after = Fragment.from(typeAfter ? typeAfter.type.create(typeAfter.attrs, after) : $pos.node(d).copy(after));
  }
  tr.step(new ReplaceStep(pos, pos, new Slice(before.append(after), depth, depth), true));
}
function canJoin(doc3, pos) {
  let $pos = doc3.resolve(pos), index2 = $pos.index();
  return joinable2($pos.nodeBefore, $pos.nodeAfter) && $pos.parent.canReplace(index2, index2 + 1);
}
function canAppendWithSubstitutedLinebreaks(a, b) {
  if (!b.content.size)
    a.type.compatibleContent(b.type);
  let match = a.contentMatchAt(a.childCount);
  let { linebreakReplacement } = a.type.schema;
  for (let i2 = 0; i2 < b.childCount; i2++) {
    let child = b.child(i2);
    let type = child.type == linebreakReplacement ? a.type.schema.nodes.text : child.type;
    match = match.matchType(type);
    if (!match)
      return false;
    if (!a.type.allowsMarks(child.marks))
      return false;
  }
  return match.validEnd;
}
function joinable2(a, b) {
  return !!(a && b && !a.isLeaf && canAppendWithSubstitutedLinebreaks(a, b));
}
function join(tr, pos, depth) {
  let convertNewlines = null;
  let { linebreakReplacement } = tr.doc.type.schema;
  let $before = tr.doc.resolve(pos - depth), beforeType = $before.node().type;
  if (linebreakReplacement && beforeType.inlineContent) {
    let pre = beforeType.whitespace == "pre";
    let supportLinebreak = !!beforeType.contentMatch.matchType(linebreakReplacement);
    if (pre && !supportLinebreak)
      convertNewlines = false;
    else if (!pre && supportLinebreak)
      convertNewlines = true;
  }
  let mapFrom = tr.steps.length;
  if (convertNewlines === false) {
    let $after = tr.doc.resolve(pos + depth);
    replaceLinebreaks(tr, $after.node(), $after.before(), mapFrom);
  }
  if (beforeType.inlineContent)
    clearIncompatible(tr, pos + depth - 1, beforeType, $before.node().contentMatchAt($before.index()), convertNewlines == null);
  let mapping = tr.mapping.slice(mapFrom), start = mapping.map(pos - depth);
  tr.step(new ReplaceStep(start, mapping.map(pos + depth, -1), Slice.empty, true));
  if (convertNewlines === true) {
    let $full = tr.doc.resolve(start);
    replaceNewlines(tr, $full.node(), $full.before(), tr.steps.length);
  }
  return tr;
}
function insertPoint(doc3, pos, nodeType) {
  let $pos = doc3.resolve(pos);
  if ($pos.parent.canReplaceWith($pos.index(), $pos.index(), nodeType))
    return pos;
  if ($pos.parentOffset == 0)
    for (let d = $pos.depth - 1; d >= 0; d--) {
      let index2 = $pos.index(d);
      if ($pos.node(d).canReplaceWith(index2, index2, nodeType))
        return $pos.before(d + 1);
      if (index2 > 0)
        return null;
    }
  if ($pos.parentOffset == $pos.parent.content.size)
    for (let d = $pos.depth - 1; d >= 0; d--) {
      let index2 = $pos.indexAfter(d);
      if ($pos.node(d).canReplaceWith(index2, index2, nodeType))
        return $pos.after(d + 1);
      if (index2 < $pos.node(d).childCount)
        return null;
    }
  return null;
}
function dropPoint(doc3, pos, slice2) {
  let $pos = doc3.resolve(pos);
  if (!slice2.content.size)
    return pos;
  let content3 = slice2.content;
  for (let i2 = 0; i2 < slice2.openStart; i2++)
    content3 = content3.firstChild.content;
  for (let pass = 1; pass <= (slice2.openStart == 0 && slice2.size ? 2 : 1); pass++) {
    for (let d = $pos.depth; d >= 0; d--) {
      let bias = d == $pos.depth ? 0 : $pos.pos <= ($pos.start(d + 1) + $pos.end(d + 1)) / 2 ? -1 : 1;
      let insertPos = $pos.index(d) + (bias > 0 ? 1 : 0);
      let parent = $pos.node(d), fits = false;
      if (pass == 1) {
        fits = parent.canReplace(insertPos, insertPos, content3);
      } else {
        let wrapping = parent.contentMatchAt(insertPos).findWrapping(content3.firstChild.type);
        fits = wrapping && parent.canReplaceWith(insertPos, insertPos, wrapping[0]);
      }
      if (fits)
        return bias == 0 ? $pos.pos : bias < 0 ? $pos.before(d + 1) : $pos.after(d + 1);
    }
  }
  return null;
}
function replaceStep(doc3, from2, to = from2, slice2 = Slice.empty) {
  if (from2 == to && !slice2.size)
    return null;
  let $from = doc3.resolve(from2), $to = doc3.resolve(to);
  if (fitsTrivially($from, $to, slice2))
    return new ReplaceStep(from2, to, slice2);
  return new Fitter($from, $to, slice2).fit();
}
function fitsTrivially($from, $to, slice2) {
  return !slice2.openStart && !slice2.openEnd && $from.start() == $to.start() && $from.parent.canReplace($from.index(), $to.index(), slice2.content);
}
var Fitter = class {
  constructor($from, $to, unplaced) {
    this.$from = $from;
    this.$to = $to;
    this.unplaced = unplaced;
    this.frontier = [];
    this.placed = Fragment.empty;
    for (let i2 = 0; i2 <= $from.depth; i2++) {
      let node2 = $from.node(i2);
      this.frontier.push({
        type: node2.type,
        match: node2.contentMatchAt($from.indexAfter(i2))
      });
    }
    for (let i2 = $from.depth; i2 > 0; i2--)
      this.placed = Fragment.from($from.node(i2).copy(this.placed));
  }
  get depth() {
    return this.frontier.length - 1;
  }
  fit() {
    while (this.unplaced.size) {
      let fit = this.findFittable();
      if (fit)
        this.placeNodes(fit);
      else
        this.openMore() || this.dropNode();
    }
    let moveInline = this.mustMoveInline(), placedSize = this.placed.size - this.depth - this.$from.depth;
    let $from = this.$from, $to = this.close(moveInline < 0 ? this.$to : $from.doc.resolve(moveInline));
    if (!$to)
      return null;
    let content3 = this.placed, openStart = $from.depth, openEnd = $to.depth;
    while (openStart && openEnd && content3.childCount == 1) {
      content3 = content3.firstChild.content;
      openStart--;
      openEnd--;
    }
    let slice2 = new Slice(content3, openStart, openEnd);
    if (moveInline > -1)
      return new ReplaceAroundStep($from.pos, moveInline, this.$to.pos, this.$to.end(), slice2, placedSize);
    if (slice2.size || $from.pos != this.$to.pos)
      return new ReplaceStep($from.pos, $to.pos, slice2);
    return null;
  }
  // Find a position on the start spine of `this.unplaced` that has
  // content that can be moved somewhere on the frontier. Returns two
  // depths, one for the slice and one for the frontier.
  findFittable() {
    let startDepth = this.unplaced.openStart;
    for (let cur = this.unplaced.content, d = 0, openEnd = this.unplaced.openEnd; d < startDepth; d++) {
      let node2 = cur.firstChild;
      if (cur.childCount > 1)
        openEnd = 0;
      if (node2.type.spec.isolating && openEnd <= d) {
        startDepth = d;
        break;
      }
      cur = node2.content;
    }
    for (let pass = 1; pass <= 2; pass++) {
      for (let sliceDepth = pass == 1 ? startDepth : this.unplaced.openStart; sliceDepth >= 0; sliceDepth--) {
        let fragment, parent = null;
        if (sliceDepth) {
          parent = contentAt(this.unplaced.content, sliceDepth - 1).firstChild;
          fragment = parent.content;
        } else {
          fragment = this.unplaced.content;
        }
        let first = fragment.firstChild;
        for (let frontierDepth = this.depth; frontierDepth >= 0; frontierDepth--) {
          let { type, match } = this.frontier[frontierDepth], wrap2, inject = null;
          if (pass == 1 && (first ? match.matchType(first.type) || (inject = match.fillBefore(Fragment.from(first), false)) : parent && type.compatibleContent(parent.type)))
            return { sliceDepth, frontierDepth, parent, inject };
          else if (pass == 2 && first && (wrap2 = match.findWrapping(first.type)))
            return { sliceDepth, frontierDepth, parent, wrap: wrap2 };
          if (parent && match.matchType(parent.type))
            break;
        }
      }
    }
  }
  openMore() {
    let { content: content3, openStart, openEnd } = this.unplaced;
    if (maxOpen(content3, -1) <= openStart)
      return false;
    if (this.unplaced.size > 1 && maxOpen(content3, 1) > openEnd)
      openEnd++;
    this.unplaced = new Slice(content3, openStart + 1, openEnd);
    return true;
  }
  dropNode() {
    let { content: content3, openStart, openEnd } = this.unplaced;
    let inner = contentAt(content3, openStart);
    if (inner.childCount <= 1 && openStart > 0) {
      let openAtEnd = content3.size - openStart <= openStart + inner.size;
      this.unplaced = new Slice(dropFromFragment(content3, openStart - 1, 1), openStart - 1, openAtEnd ? openStart - 1 : openEnd);
    } else {
      this.unplaced = new Slice(dropFromFragment(content3, openStart, 1), openStart, openEnd);
    }
  }
  // Move content from the unplaced slice at `sliceDepth` to the
  // frontier node at `frontierDepth`. Close that frontier node when
  // applicable.
  placeNodes({ sliceDepth, frontierDepth, parent, inject, wrap: wrap2 }) {
    while (this.depth > frontierDepth)
      this.closeFrontierNode();
    if (wrap2)
      for (let i2 = 0; i2 < wrap2.length; i2++)
        this.openFrontierNode(wrap2[i2]);
    let slice2 = this.unplaced, fragment = parent ? parent.content : slice2.content;
    let openStart = slice2.openStart - sliceDepth;
    let taken = 0, add = [];
    let { match, type } = this.frontier[frontierDepth];
    if (inject) {
      for (let i2 = 0; i2 < inject.childCount; i2++)
        add.push(inject.child(i2));
      match = match.matchFragment(inject);
    }
    let openEndCount = fragment.size + sliceDepth - (slice2.content.size - slice2.openEnd);
    while (taken < fragment.childCount) {
      let next = fragment.child(taken), matches2 = match.matchType(next.type);
      if (!matches2)
        break;
      taken++;
      if (taken > 1 || openStart == 0 || next.content.size) {
        match = matches2;
        add.push(closeNodeStart(next.mark(type.allowedMarks(next.marks)), taken == 1 ? openStart : 0, taken == fragment.childCount ? openEndCount : -1));
      }
    }
    let toEnd = taken == fragment.childCount;
    if (!toEnd)
      openEndCount = -1;
    this.placed = addToFragment(this.placed, frontierDepth, Fragment.from(add));
    this.frontier[frontierDepth].match = match;
    if (toEnd && openEndCount < 0 && parent && parent.type == this.frontier[this.depth].type && this.frontier.length > 1)
      this.closeFrontierNode();
    for (let i2 = 0, cur = fragment; i2 < openEndCount; i2++) {
      let node2 = cur.lastChild;
      this.frontier.push({ type: node2.type, match: node2.contentMatchAt(node2.childCount) });
      cur = node2.content;
    }
    this.unplaced = !toEnd ? new Slice(dropFromFragment(slice2.content, sliceDepth, taken), slice2.openStart, slice2.openEnd) : sliceDepth == 0 ? Slice.empty : new Slice(dropFromFragment(slice2.content, sliceDepth - 1, 1), sliceDepth - 1, openEndCount < 0 ? slice2.openEnd : sliceDepth - 1);
  }
  mustMoveInline() {
    if (!this.$to.parent.isTextblock)
      return -1;
    let top = this.frontier[this.depth], level;
    if (!top.type.isTextblock || !contentAfterFits(this.$to, this.$to.depth, top.type, top.match, false) || this.$to.depth == this.depth && (level = this.findCloseLevel(this.$to)) && level.depth == this.depth)
      return -1;
    let { depth } = this.$to, after = this.$to.after(depth);
    while (depth > 1 && after == this.$to.end(--depth))
      ++after;
    return after;
  }
  findCloseLevel($to) {
    scan: for (let i2 = Math.min(this.depth, $to.depth); i2 >= 0; i2--) {
      let { match, type } = this.frontier[i2];
      let dropInner = i2 < $to.depth && $to.end(i2 + 1) == $to.pos + ($to.depth - (i2 + 1));
      let fit = contentAfterFits($to, i2, type, match, dropInner);
      if (!fit)
        continue;
      for (let d = i2 - 1; d >= 0; d--) {
        let { match: match2, type: type2 } = this.frontier[d];
        let matches2 = contentAfterFits($to, d, type2, match2, true);
        if (!matches2 || matches2.childCount)
          continue scan;
      }
      return { depth: i2, fit, move: dropInner ? $to.doc.resolve($to.after(i2 + 1)) : $to };
    }
  }
  close($to) {
    let close2 = this.findCloseLevel($to);
    if (!close2)
      return null;
    while (this.depth > close2.depth)
      this.closeFrontierNode();
    if (close2.fit.childCount)
      this.placed = addToFragment(this.placed, close2.depth, close2.fit);
    $to = close2.move;
    for (let d = close2.depth + 1; d <= $to.depth; d++) {
      let node2 = $to.node(d), add = node2.type.contentMatch.fillBefore(node2.content, true, $to.index(d));
      this.openFrontierNode(node2.type, node2.attrs, add);
    }
    return $to;
  }
  openFrontierNode(type, attrs = null, content3) {
    let top = this.frontier[this.depth];
    top.match = top.match.matchType(type);
    this.placed = addToFragment(this.placed, this.depth, Fragment.from(type.create(attrs, content3)));
    this.frontier.push({ type, match: type.contentMatch });
  }
  closeFrontierNode() {
    let open = this.frontier.pop();
    let add = open.match.fillBefore(Fragment.empty, true);
    if (add.childCount)
      this.placed = addToFragment(this.placed, this.frontier.length, add);
  }
};
function dropFromFragment(fragment, depth, count) {
  if (depth == 0)
    return fragment.cutByIndex(count, fragment.childCount);
  return fragment.replaceChild(0, fragment.firstChild.copy(dropFromFragment(fragment.firstChild.content, depth - 1, count)));
}
function addToFragment(fragment, depth, content3) {
  if (depth == 0)
    return fragment.append(content3);
  return fragment.replaceChild(fragment.childCount - 1, fragment.lastChild.copy(addToFragment(fragment.lastChild.content, depth - 1, content3)));
}
function contentAt(fragment, depth) {
  for (let i2 = 0; i2 < depth; i2++)
    fragment = fragment.firstChild.content;
  return fragment;
}
function closeNodeStart(node2, openStart, openEnd) {
  if (openStart <= 0)
    return node2;
  let frag = node2.content;
  if (openStart > 1)
    frag = frag.replaceChild(0, closeNodeStart(frag.firstChild, openStart - 1, frag.childCount == 1 ? openEnd - 1 : 0));
  if (openStart > 0) {
    frag = node2.type.contentMatch.fillBefore(frag).append(frag);
    if (openEnd <= 0)
      frag = frag.append(node2.type.contentMatch.matchFragment(frag).fillBefore(Fragment.empty, true));
  }
  return node2.copy(frag);
}
function contentAfterFits($to, depth, type, match, open) {
  let node2 = $to.node(depth), index2 = open ? $to.indexAfter(depth) : $to.index(depth);
  if (index2 == node2.childCount && !type.compatibleContent(node2.type))
    return null;
  let fit = match.fillBefore(node2.content, true, index2);
  return fit && !invalidMarks(type, node2.content, index2) ? fit : null;
}
function invalidMarks(type, fragment, start) {
  for (let i2 = start; i2 < fragment.childCount; i2++)
    if (!type.allowsMarks(fragment.child(i2).marks))
      return true;
  return false;
}
function definesContent(type) {
  return type.spec.defining || type.spec.definingForContent;
}
function maxOpen(frag, side) {
  for (let count = 0; ; count++) {
    let ch = side < 0 ? frag.firstChild : frag.lastChild;
    if (!ch || ch.isAtom)
      return count;
    frag = ch.content;
  }
}
function replaceRange(tr, from2, to, slice2) {
  if (!slice2.size)
    return tr.deleteRange(from2, to);
  let $from = tr.doc.resolve(from2), $to = tr.doc.resolve(to);
  if (fitsTrivially($from, $to, slice2))
    return tr.step(new ReplaceStep(from2, to, slice2));
  let targetDepths = coveredDepths($from, $to);
  if (targetDepths[targetDepths.length - 1] == 0)
    targetDepths.pop();
  let preferredTarget = -($from.depth + 1);
  targetDepths.unshift(preferredTarget);
  for (let d = $from.depth, pos = $from.pos - 1; d > 0; d--, pos--) {
    let spec = $from.node(d).type.spec;
    if (spec.defining || spec.definingAsContext || spec.isolating)
      break;
    if (targetDepths.indexOf(d) > -1)
      preferredTarget = d;
    else if ($from.before(d) == pos)
      targetDepths.splice(1, 0, -d);
  }
  let preferredTargetIndex = targetDepths.indexOf(preferredTarget);
  let leftNodes = [], preferredDepth = slice2.openStart;
  for (let content3 = slice2.content, i2 = 0; ; i2++) {
    let node2 = content3.firstChild;
    leftNodes.push(node2);
    if (i2 == slice2.openStart)
      break;
    content3 = node2.content;
  }
  for (let d = preferredDepth - 1; d >= 0; d--) {
    let leftNode = leftNodes[d], def = definesContent(leftNode.type);
    if (def && !leftNode.sameMarkup($from.node(Math.abs(preferredTarget) - 1)))
      preferredDepth = d;
    else if (def || !leftNode.type.isTextblock)
      break;
  }
  for (let j = slice2.openStart; j >= 0; j--) {
    let openDepth = (j + preferredDepth + 1) % (slice2.openStart + 1);
    let insert = leftNodes[openDepth];
    if (!insert)
      continue;
    for (let i2 = 0; i2 < targetDepths.length; i2++) {
      let targetDepth = targetDepths[(i2 + preferredTargetIndex) % targetDepths.length], expand = true;
      if (targetDepth < 0) {
        expand = false;
        targetDepth = -targetDepth;
      }
      let parent = $from.node(targetDepth - 1), index2 = $from.index(targetDepth - 1);
      if (parent.canReplaceWith(index2, index2, insert.type, insert.marks))
        return tr.replace($from.before(targetDepth), expand ? $to.after(targetDepth) : to, new Slice(closeFragment(slice2.content, 0, slice2.openStart, openDepth), openDepth, slice2.openEnd));
    }
  }
  let startSteps = tr.steps.length;
  for (let i2 = targetDepths.length - 1; i2 >= 0; i2--) {
    tr.replace(from2, to, slice2);
    if (tr.steps.length > startSteps)
      break;
    let depth = targetDepths[i2];
    if (depth < 0)
      continue;
    from2 = $from.before(depth);
    to = $to.after(depth);
  }
}
function closeFragment(fragment, depth, oldOpen, newOpen, parent) {
  if (depth < oldOpen) {
    let first = fragment.firstChild;
    fragment = fragment.replaceChild(0, first.copy(closeFragment(first.content, depth + 1, oldOpen, newOpen, first)));
  }
  if (depth > newOpen) {
    let match = parent.contentMatchAt(0);
    let start = match.fillBefore(fragment).append(fragment);
    fragment = start.append(match.matchFragment(start).fillBefore(Fragment.empty, true));
  }
  return fragment;
}
function replaceRangeWith(tr, from2, to, node2) {
  if (!node2.isInline && from2 == to && tr.doc.resolve(from2).parent.content.size) {
    let point3 = insertPoint(tr.doc, from2, node2.type);
    if (point3 != null)
      from2 = to = point3;
  }
  tr.replaceRange(from2, to, new Slice(Fragment.from(node2), 0, 0));
}
function deleteRange(tr, from2, to) {
  let $from = tr.doc.resolve(from2), $to = tr.doc.resolve(to);
  if ($from.parent.isTextblock && $to.parent.isTextblock && $from.start() != $to.start() && $from.parentOffset == 0 && $to.parentOffset == 0) {
    let shared = $from.sharedDepth(to), isolated = false;
    for (let d = $from.depth; d > shared; d--)
      if ($from.node(d).type.spec.isolating)
        isolated = true;
    for (let d = $to.depth; d > shared; d--)
      if ($to.node(d).type.spec.isolating)
        isolated = true;
    if (!isolated) {
      for (let d = $from.depth; d > 0 && from2 == $from.start(d); d--)
        from2 = $from.before(d);
      for (let d = $to.depth; d > 0 && to == $to.start(d); d--)
        to = $to.before(d);
      $from = tr.doc.resolve(from2);
      $to = tr.doc.resolve(to);
    }
  }
  let covered = coveredDepths($from, $to);
  for (let i2 = 0; i2 < covered.length; i2++) {
    let depth = covered[i2], last = i2 == covered.length - 1;
    if (last && depth == 0 || $from.node(depth).type.contentMatch.validEnd)
      return tr.delete($from.start(depth), $to.end(depth));
    if (depth > 0 && (last || $from.node(depth - 1).canReplace($from.index(depth - 1), $to.indexAfter(depth - 1))))
      return tr.delete($from.before(depth), $to.after(depth));
  }
  for (let d = 1; d <= $from.depth && d <= $to.depth; d++) {
    if (from2 - $from.start(d) == $from.depth - d && to > $from.end(d) && $to.end(d) - to != $to.depth - d && $from.start(d - 1) == $to.start(d - 1) && $from.node(d - 1).canReplace($from.index(d - 1), $to.index(d - 1)))
      return tr.delete($from.before(d), to);
  }
  tr.delete(from2, to);
}
function coveredDepths($from, $to) {
  let result = [], minDepth = Math.min($from.depth, $to.depth);
  for (let d = minDepth; d >= 0; d--) {
    let start = $from.start(d);
    if (start < $from.pos - ($from.depth - d) || $to.end(d) > $to.pos + ($to.depth - d) || $from.node(d).type.spec.isolating || $to.node(d).type.spec.isolating)
      break;
    if (start == $to.start(d) || d == $from.depth && d == $to.depth && $from.parent.inlineContent && $to.parent.inlineContent && d && $to.start(d - 1) == start - 1)
      result.push(d);
  }
  return result;
}
var AttrStep = class _AttrStep extends Step {
  /**
  Construct an attribute step.
  */
  constructor(pos, attr, value) {
    super();
    this.pos = pos;
    this.attr = attr;
    this.value = value;
  }
  apply(doc3) {
    let node2 = doc3.nodeAt(this.pos);
    if (!node2)
      return StepResult.fail("No node at attribute step's position");
    let attrs = /* @__PURE__ */ Object.create(null);
    for (let name in node2.attrs)
      attrs[name] = node2.attrs[name];
    attrs[this.attr] = this.value;
    let updated = node2.type.create(attrs, null, node2.marks);
    return StepResult.fromReplace(doc3, this.pos, this.pos + 1, new Slice(Fragment.from(updated), 0, node2.isLeaf ? 0 : 1));
  }
  getMap() {
    return StepMap.empty;
  }
  invert(doc3) {
    return new _AttrStep(this.pos, this.attr, doc3.nodeAt(this.pos).attrs[this.attr]);
  }
  map(mapping) {
    let pos = mapping.mapResult(this.pos, 1);
    return pos.deletedAfter ? null : new _AttrStep(pos.pos, this.attr, this.value);
  }
  toJSON() {
    return { stepType: "attr", pos: this.pos, attr: this.attr, value: this.value };
  }
  static fromJSON(schema2, json) {
    if (typeof json.pos != "number" || typeof json.attr != "string")
      throw new RangeError("Invalid input for AttrStep.fromJSON");
    return new _AttrStep(json.pos, json.attr, json.value);
  }
};
Step.jsonID("attr", AttrStep);
var DocAttrStep = class _DocAttrStep extends Step {
  /**
  Construct an attribute step.
  */
  constructor(attr, value) {
    super();
    this.attr = attr;
    this.value = value;
  }
  apply(doc3) {
    let attrs = /* @__PURE__ */ Object.create(null);
    for (let name in doc3.attrs)
      attrs[name] = doc3.attrs[name];
    attrs[this.attr] = this.value;
    let updated = doc3.type.create(attrs, doc3.content, doc3.marks);
    return StepResult.ok(updated);
  }
  getMap() {
    return StepMap.empty;
  }
  invert(doc3) {
    return new _DocAttrStep(this.attr, doc3.attrs[this.attr]);
  }
  map(mapping) {
    return this;
  }
  toJSON() {
    return { stepType: "docAttr", attr: this.attr, value: this.value };
  }
  static fromJSON(schema2, json) {
    if (typeof json.attr != "string")
      throw new RangeError("Invalid input for DocAttrStep.fromJSON");
    return new _DocAttrStep(json.attr, json.value);
  }
};
Step.jsonID("docAttr", DocAttrStep);
var TransformError = class extends Error {
};
TransformError = function TransformError2(message) {
  let err = Error.call(this, message);
  err.__proto__ = TransformError2.prototype;
  return err;
};
TransformError.prototype = Object.create(Error.prototype);
TransformError.prototype.constructor = TransformError;
TransformError.prototype.name = "TransformError";
var Transform = class {
  /**
  Create a transform that starts with the given document.
  */
  constructor(doc3) {
    this.doc = doc3;
    this.steps = [];
    this.docs = [];
    this.mapping = new Mapping();
  }
  /**
  The starting document.
  */
  get before() {
    return this.docs.length ? this.docs[0] : this.doc;
  }
  /**
  Apply a new step in this transform, saving the result. Throws an
  error when the step fails.
  */
  step(step) {
    let result = this.maybeStep(step);
    if (result.failed)
      throw new TransformError(result.failed);
    return this;
  }
  /**
  Try to apply a step in this transformation, ignoring it if it
  fails. Returns the step result.
  */
  maybeStep(step) {
    let result = step.apply(this.doc);
    if (!result.failed)
      this.addStep(step, result.doc);
    return result;
  }
  /**
  True when the document has been changed (when there are any
  steps).
  */
  get docChanged() {
    return this.steps.length > 0;
  }
  /**
  Return a single range, in post-transform document positions,
  that covers all content changed by this transform. Returns null
  if no replacements are made. Note that this will ignore changes
  that add/remove marks without replacing the underlying content.
  */
  changedRange() {
    let from2 = 1e9, to = -1e9;
    for (let i2 = 0; i2 < this.mapping.maps.length; i2++) {
      let map5 = this.mapping.maps[i2];
      if (i2) {
        from2 = map5.map(from2, 1);
        to = map5.map(to, -1);
      }
      map5.forEach((_f, _t, fromB, toB) => {
        from2 = Math.min(from2, fromB);
        to = Math.max(to, toB);
      });
    }
    return from2 == 1e9 ? null : { from: from2, to };
  }
  /**
  @internal
  */
  addStep(step, doc3) {
    this.docs.push(this.doc);
    this.steps.push(step);
    this.mapping.appendMap(step.getMap());
    this.doc = doc3;
  }
  /**
  Replace the part of the document between `from` and `to` with the
  given `slice`.
  */
  replace(from2, to = from2, slice2 = Slice.empty) {
    let step = replaceStep(this.doc, from2, to, slice2);
    if (step)
      this.step(step);
    return this;
  }
  /**
  Replace the given range with the given content, which may be a
  fragment, node, or array of nodes.
  */
  replaceWith(from2, to, content3) {
    return this.replace(from2, to, new Slice(Fragment.from(content3), 0, 0));
  }
  /**
  Delete the content between the given positions.
  */
  delete(from2, to) {
    return this.replace(from2, to, Slice.empty);
  }
  /**
  Insert the given content at the given position.
  */
  insert(pos, content3) {
    return this.replaceWith(pos, pos, content3);
  }
  /**
  Replace a range of the document with a given slice, using
  `from`, `to`, and the slice's
  [`openStart`](https://prosemirror.net/docs/ref/#model.Slice.openStart) property as hints, rather
  than fixed start and end points. This method may grow the
  replaced area or close open nodes in the slice in order to get a
  fit that is more in line with WYSIWYG expectations, by dropping
  fully covered parent nodes of the replaced region when they are
  marked [non-defining as
  context](https://prosemirror.net/docs/ref/#model.NodeSpec.definingAsContext), or including an
  open parent node from the slice that _is_ marked as [defining
  its content](https://prosemirror.net/docs/ref/#model.NodeSpec.definingForContent).
  
  This is the method, for example, to handle paste. The similar
  [`replace`](https://prosemirror.net/docs/ref/#transform.Transform.replace) method is a more
  primitive tool which will _not_ move the start and end of its given
  range, and is useful in situations where you need more precise
  control over what happens.
  */
  replaceRange(from2, to, slice2) {
    replaceRange(this, from2, to, slice2);
    return this;
  }
  /**
  Replace the given range with a node, but use `from` and `to` as
  hints, rather than precise positions. When from and to are the same
  and are at the start or end of a parent node in which the given
  node doesn't fit, this method may _move_ them out towards a parent
  that does allow the given node to be placed. When the given range
  completely covers a parent node, this method may completely replace
  that parent node.
  */
  replaceRangeWith(from2, to, node2) {
    replaceRangeWith(this, from2, to, node2);
    return this;
  }
  /**
  Delete the given range, expanding it to cover fully covered
  parent nodes until a valid replace is found.
  */
  deleteRange(from2, to) {
    deleteRange(this, from2, to);
    return this;
  }
  /**
  Split the content in the given range off from its parent, if there
  is sibling content before or after it, and move it up the tree to
  the depth specified by `target`. You'll probably want to use
  [`liftTarget`](https://prosemirror.net/docs/ref/#transform.liftTarget) to compute `target`, to make
  sure the lift is valid.
  */
  lift(range, target) {
    lift(this, range, target);
    return this;
  }
  /**
  Join the blocks around the given position. If depth is 2, their
  last and first siblings are also joined, and so on.
  */
  join(pos, depth = 1) {
    join(this, pos, depth);
    return this;
  }
  /**
  Wrap the given [range](https://prosemirror.net/docs/ref/#model.NodeRange) in the given set of wrappers.
  The wrappers are assumed to be valid in this position, and should
  probably be computed with [`findWrapping`](https://prosemirror.net/docs/ref/#transform.findWrapping).
  */
  wrap(range, wrappers) {
    wrap(this, range, wrappers);
    return this;
  }
  /**
  Set the type of all textblocks (partly) between `from` and `to` to
  the given node type with the given attributes.
  */
  setBlockType(from2, to = from2, type, attrs = null) {
    setBlockType(this, from2, to, type, attrs);
    return this;
  }
  /**
  Change the type, attributes, and/or marks of the node at `pos`.
  When `type` isn't given, the existing node type is preserved,
  */
  setNodeMarkup(pos, type, attrs = null, marks) {
    setNodeMarkup(this, pos, type, attrs, marks);
    return this;
  }
  /**
  Set a single attribute on a given node to a new value.
  The `pos` addresses the document content. Use `setDocAttribute`
  to set attributes on the document itself.
  */
  setNodeAttribute(pos, attr, value) {
    this.step(new AttrStep(pos, attr, value));
    return this;
  }
  /**
  Set a single attribute on the document to a new value.
  */
  setDocAttribute(attr, value) {
    this.step(new DocAttrStep(attr, value));
    return this;
  }
  /**
  Add a mark to the node at position `pos`.
  */
  addNodeMark(pos, mark) {
    this.step(new AddNodeMarkStep(pos, mark));
    return this;
  }
  /**
  Remove a mark (or all marks of the given type) from the node at
  position `pos`.
  */
  removeNodeMark(pos, mark) {
    let node2 = this.doc.nodeAt(pos);
    if (!node2)
      throw new RangeError("No node at position " + pos);
    if (mark instanceof Mark) {
      if (mark.isInSet(node2.marks))
        this.step(new RemoveNodeMarkStep(pos, mark));
    } else {
      let set = node2.marks, found2, steps = [];
      while (found2 = mark.isInSet(set)) {
        steps.push(new RemoveNodeMarkStep(pos, found2));
        set = found2.removeFromSet(set);
      }
      for (let i2 = steps.length - 1; i2 >= 0; i2--)
        this.step(steps[i2]);
    }
    return this;
  }
  /**
  Split the node at the given position, and optionally, if `depth` is
  greater than one, any number of nodes above that. By default, the
  parts split off will inherit the node type of the original node.
  This can be changed by passing an array of types and attributes to
  use after the split (with the outermost nodes coming first).
  */
  split(pos, depth = 1, typesAfter) {
    split(this, pos, depth, typesAfter);
    return this;
  }
  /**
  Add the given mark to the inline content between `from` and `to`.
  */
  addMark(from2, to, mark) {
    addMark(this, from2, to, mark);
    return this;
  }
  /**
  Remove marks from inline nodes between `from` and `to`. When
  `mark` is a single mark, remove precisely that mark. When it is
  a mark type, remove all marks of that type. When it is null,
  remove all marks of any type.
  */
  removeMark(from2, to, mark) {
    removeMark(this, from2, to, mark);
    return this;
  }
  /**
  Removes all marks and nodes from the content of the node at
  `pos` that don't match the given new parent node type. Accepts
  an optional starting [content match](https://prosemirror.net/docs/ref/#model.ContentMatch) as
  third argument.
  */
  clearIncompatible(pos, parentType, match) {
    clearIncompatible(this, pos, parentType, match);
    return this;
  }
};

// node_modules/.pnpm/prosemirror-state@1.4.4/node_modules/prosemirror-state/dist/index.js
var classesById = /* @__PURE__ */ Object.create(null);
var Selection = class {
  /**
  Initialize a selection with the head and anchor and ranges. If no
  ranges are given, constructs a single range across `$anchor` and
  `$head`.
  */
  constructor($anchor, $head, ranges) {
    this.$anchor = $anchor;
    this.$head = $head;
    this.ranges = ranges || [new SelectionRange($anchor.min($head), $anchor.max($head))];
  }
  /**
  The selection's anchor, as an unresolved position.
  */
  get anchor() {
    return this.$anchor.pos;
  }
  /**
  The selection's head.
  */
  get head() {
    return this.$head.pos;
  }
  /**
  The lower bound of the selection's main range.
  */
  get from() {
    return this.$from.pos;
  }
  /**
  The upper bound of the selection's main range.
  */
  get to() {
    return this.$to.pos;
  }
  /**
  The resolved lower  bound of the selection's main range.
  */
  get $from() {
    return this.ranges[0].$from;
  }
  /**
  The resolved upper bound of the selection's main range.
  */
  get $to() {
    return this.ranges[0].$to;
  }
  /**
  Indicates whether the selection contains any content.
  */
  get empty() {
    let ranges = this.ranges;
    for (let i2 = 0; i2 < ranges.length; i2++)
      if (ranges[i2].$from.pos != ranges[i2].$to.pos)
        return false;
    return true;
  }
  /**
  Get the content of this selection as a slice.
  */
  content() {
    return this.$from.doc.slice(this.from, this.to, true);
  }
  /**
  Replace the selection with a slice or, if no slice is given,
  delete the selection. Will append to the given transaction.
  */
  replace(tr, content3 = Slice.empty) {
    let lastNode = content3.content.lastChild, lastParent = null;
    for (let i2 = 0; i2 < content3.openEnd; i2++) {
      lastParent = lastNode;
      lastNode = lastNode.lastChild;
    }
    let mapFrom = tr.steps.length, ranges = this.ranges;
    for (let i2 = 0; i2 < ranges.length; i2++) {
      let { $from, $to } = ranges[i2], mapping = tr.mapping.slice(mapFrom);
      tr.replaceRange(mapping.map($from.pos), mapping.map($to.pos), i2 ? Slice.empty : content3);
      if (i2 == 0)
        selectionToInsertionEnd(tr, mapFrom, (lastNode ? lastNode.isInline : lastParent && lastParent.isTextblock) ? -1 : 1);
    }
  }
  /**
  Replace the selection with the given node, appending the changes
  to the given transaction.
  */
  replaceWith(tr, node2) {
    let mapFrom = tr.steps.length, ranges = this.ranges;
    for (let i2 = 0; i2 < ranges.length; i2++) {
      let { $from, $to } = ranges[i2], mapping = tr.mapping.slice(mapFrom);
      let from2 = mapping.map($from.pos), to = mapping.map($to.pos);
      if (i2) {
        tr.deleteRange(from2, to);
      } else {
        tr.replaceRangeWith(from2, to, node2);
        selectionToInsertionEnd(tr, mapFrom, node2.isInline ? -1 : 1);
      }
    }
  }
  /**
  Find a valid cursor or leaf node selection starting at the given
  position and searching back if `dir` is negative, and forward if
  positive. When `textOnly` is true, only consider cursor
  selections. Will return null when no valid selection position is
  found.
  */
  static findFrom($pos, dir, textOnly = false) {
    let inner = $pos.parent.inlineContent ? new TextSelection($pos) : findSelectionIn($pos.node(0), $pos.parent, $pos.pos, $pos.index(), dir, textOnly);
    if (inner)
      return inner;
    for (let depth = $pos.depth - 1; depth >= 0; depth--) {
      let found2 = dir < 0 ? findSelectionIn($pos.node(0), $pos.node(depth), $pos.before(depth + 1), $pos.index(depth), dir, textOnly) : findSelectionIn($pos.node(0), $pos.node(depth), $pos.after(depth + 1), $pos.index(depth) + 1, dir, textOnly);
      if (found2)
        return found2;
    }
    return null;
  }
  /**
  Find a valid cursor or leaf node selection near the given
  position. Searches forward first by default, but if `bias` is
  negative, it will search backwards first.
  */
  static near($pos, bias = 1) {
    return this.findFrom($pos, bias) || this.findFrom($pos, -bias) || new AllSelection($pos.node(0));
  }
  /**
  Find the cursor or leaf node selection closest to the start of
  the given document. Will return an
  [`AllSelection`](https://prosemirror.net/docs/ref/#state.AllSelection) if no valid position
  exists.
  */
  static atStart(doc3) {
    return findSelectionIn(doc3, doc3, 0, 0, 1) || new AllSelection(doc3);
  }
  /**
  Find the cursor or leaf node selection closest to the end of the
  given document.
  */
  static atEnd(doc3) {
    return findSelectionIn(doc3, doc3, doc3.content.size, doc3.childCount, -1) || new AllSelection(doc3);
  }
  /**
  Deserialize the JSON representation of a selection. Must be
  implemented for custom classes (as a static class method).
  */
  static fromJSON(doc3, json) {
    if (!json || !json.type)
      throw new RangeError("Invalid input for Selection.fromJSON");
    let cls = classesById[json.type];
    if (!cls)
      throw new RangeError(`No selection type ${json.type} defined`);
    return cls.fromJSON(doc3, json);
  }
  /**
  To be able to deserialize selections from JSON, custom selection
  classes must register themselves with an ID string, so that they
  can be disambiguated. Try to pick something that's unlikely to
  clash with classes from other modules.
  */
  static jsonID(id, selectionClass) {
    if (id in classesById)
      throw new RangeError("Duplicate use of selection JSON ID " + id);
    classesById[id] = selectionClass;
    selectionClass.prototype.jsonID = id;
    return selectionClass;
  }
  /**
  Get a [bookmark](https://prosemirror.net/docs/ref/#state.SelectionBookmark) for this selection,
  which is a value that can be mapped without having access to a
  current document, and later resolved to a real selection for a
  given document again. (This is used mostly by the history to
  track and restore old selections.) The default implementation of
  this method just converts the selection to a text selection and
  returns the bookmark for that.
  */
  getBookmark() {
    return TextSelection.between(this.$anchor, this.$head).getBookmark();
  }
};
Selection.prototype.visible = true;
var SelectionRange = class {
  /**
  Create a range.
  */
  constructor($from, $to) {
    this.$from = $from;
    this.$to = $to;
  }
};
var warnedAboutTextSelection = false;
function checkTextSelection($pos) {
  if (!warnedAboutTextSelection && !$pos.parent.inlineContent) {
    warnedAboutTextSelection = true;
    console["warn"]("TextSelection endpoint not pointing into a node with inline content (" + $pos.parent.type.name + ")");
  }
}
var TextSelection = class _TextSelection extends Selection {
  /**
  Construct a text selection between the given points.
  */
  constructor($anchor, $head = $anchor) {
    checkTextSelection($anchor);
    checkTextSelection($head);
    super($anchor, $head);
  }
  /**
  Returns a resolved position if this is a cursor selection (an
  empty text selection), and null otherwise.
  */
  get $cursor() {
    return this.$anchor.pos == this.$head.pos ? this.$head : null;
  }
  map(doc3, mapping) {
    let $head = doc3.resolve(mapping.map(this.head));
    if (!$head.parent.inlineContent)
      return Selection.near($head);
    let $anchor = doc3.resolve(mapping.map(this.anchor));
    return new _TextSelection($anchor.parent.inlineContent ? $anchor : $head, $head);
  }
  replace(tr, content3 = Slice.empty) {
    super.replace(tr, content3);
    if (content3 == Slice.empty) {
      let marks = this.$from.marksAcross(this.$to);
      if (marks)
        tr.ensureMarks(marks);
    }
  }
  eq(other) {
    return other instanceof _TextSelection && other.anchor == this.anchor && other.head == this.head;
  }
  getBookmark() {
    return new TextBookmark(this.anchor, this.head);
  }
  toJSON() {
    return { type: "text", anchor: this.anchor, head: this.head };
  }
  /**
  @internal
  */
  static fromJSON(doc3, json) {
    if (typeof json.anchor != "number" || typeof json.head != "number")
      throw new RangeError("Invalid input for TextSelection.fromJSON");
    return new _TextSelection(doc3.resolve(json.anchor), doc3.resolve(json.head));
  }
  /**
  Create a text selection from non-resolved positions.
  */
  static create(doc3, anchor, head = anchor) {
    let $anchor = doc3.resolve(anchor);
    return new this($anchor, head == anchor ? $anchor : doc3.resolve(head));
  }
  /**
  Return a text selection that spans the given positions or, if
  they aren't text positions, find a text selection near them.
  `bias` determines whether the method searches forward (default)
  or backwards (negative number) first. Will fall back to calling
  [`Selection.near`](https://prosemirror.net/docs/ref/#state.Selection^near) when the document
  doesn't contain a valid text position.
  */
  static between($anchor, $head, bias) {
    let dPos = $anchor.pos - $head.pos;
    if (!bias || dPos)
      bias = dPos >= 0 ? 1 : -1;
    if (!$head.parent.inlineContent) {
      let found2 = Selection.findFrom($head, bias, true) || Selection.findFrom($head, -bias, true);
      if (found2)
        $head = found2.$head;
      else
        return Selection.near($head, bias);
    }
    if (!$anchor.parent.inlineContent) {
      if (dPos == 0) {
        $anchor = $head;
      } else {
        $anchor = (Selection.findFrom($anchor, -bias, true) || Selection.findFrom($anchor, bias, true)).$anchor;
        if ($anchor.pos < $head.pos != dPos < 0)
          $anchor = $head;
      }
    }
    return new _TextSelection($anchor, $head);
  }
};
Selection.jsonID("text", TextSelection);
var TextBookmark = class _TextBookmark {
  constructor(anchor, head) {
    this.anchor = anchor;
    this.head = head;
  }
  map(mapping) {
    return new _TextBookmark(mapping.map(this.anchor), mapping.map(this.head));
  }
  resolve(doc3) {
    return TextSelection.between(doc3.resolve(this.anchor), doc3.resolve(this.head));
  }
};
var NodeSelection = class _NodeSelection extends Selection {
  /**
  Create a node selection. Does not verify the validity of its
  argument.
  */
  constructor($pos) {
    let node2 = $pos.nodeAfter;
    let $end = $pos.node(0).resolve($pos.pos + node2.nodeSize);
    super($pos, $end);
    this.node = node2;
  }
  map(doc3, mapping) {
    let { deleted, pos } = mapping.mapResult(this.anchor);
    let $pos = doc3.resolve(pos);
    if (deleted)
      return Selection.near($pos);
    return new _NodeSelection($pos);
  }
  content() {
    return new Slice(Fragment.from(this.node), 0, 0);
  }
  eq(other) {
    return other instanceof _NodeSelection && other.anchor == this.anchor;
  }
  toJSON() {
    return { type: "node", anchor: this.anchor };
  }
  getBookmark() {
    return new NodeBookmark(this.anchor);
  }
  /**
  @internal
  */
  static fromJSON(doc3, json) {
    if (typeof json.anchor != "number")
      throw new RangeError("Invalid input for NodeSelection.fromJSON");
    return new _NodeSelection(doc3.resolve(json.anchor));
  }
  /**
  Create a node selection from non-resolved positions.
  */
  static create(doc3, from2) {
    return new _NodeSelection(doc3.resolve(from2));
  }
  /**
  Determines whether the given node may be selected as a node
  selection.
  */
  static isSelectable(node2) {
    return !node2.isText && node2.type.spec.selectable !== false;
  }
};
NodeSelection.prototype.visible = false;
Selection.jsonID("node", NodeSelection);
var NodeBookmark = class _NodeBookmark {
  constructor(anchor) {
    this.anchor = anchor;
  }
  map(mapping) {
    let { deleted, pos } = mapping.mapResult(this.anchor);
    return deleted ? new TextBookmark(pos, pos) : new _NodeBookmark(pos);
  }
  resolve(doc3) {
    let $pos = doc3.resolve(this.anchor), node2 = $pos.nodeAfter;
    if (node2 && NodeSelection.isSelectable(node2))
      return new NodeSelection($pos);
    return Selection.near($pos);
  }
};
var AllSelection = class _AllSelection extends Selection {
  /**
  Create an all-selection over the given document.
  */
  constructor(doc3) {
    super(doc3.resolve(0), doc3.resolve(doc3.content.size));
  }
  replace(tr, content3 = Slice.empty) {
    if (content3 == Slice.empty) {
      tr.delete(0, tr.doc.content.size);
      let sel = Selection.atStart(tr.doc);
      if (!sel.eq(tr.selection))
        tr.setSelection(sel);
    } else {
      super.replace(tr, content3);
    }
  }
  toJSON() {
    return { type: "all" };
  }
  /**
  @internal
  */
  static fromJSON(doc3) {
    return new _AllSelection(doc3);
  }
  map(doc3) {
    return new _AllSelection(doc3);
  }
  eq(other) {
    return other instanceof _AllSelection;
  }
  getBookmark() {
    return AllBookmark;
  }
};
Selection.jsonID("all", AllSelection);
var AllBookmark = {
  map() {
    return this;
  },
  resolve(doc3) {
    return new AllSelection(doc3);
  }
};
function findSelectionIn(doc3, node2, pos, index2, dir, text4 = false) {
  if (node2.inlineContent)
    return TextSelection.create(doc3, pos);
  for (let i2 = index2 - (dir > 0 ? 0 : 1); dir > 0 ? i2 < node2.childCount : i2 >= 0; i2 += dir) {
    let child = node2.child(i2);
    if (!child.isAtom) {
      let inner = findSelectionIn(doc3, child, pos + dir, dir < 0 ? child.childCount : 0, dir, text4);
      if (inner)
        return inner;
    } else if (!text4 && NodeSelection.isSelectable(child)) {
      return NodeSelection.create(doc3, pos - (dir < 0 ? child.nodeSize : 0));
    }
    pos += child.nodeSize * dir;
  }
  return null;
}
function selectionToInsertionEnd(tr, startLen, bias) {
  let last = tr.steps.length - 1;
  if (last < startLen)
    return;
  let step = tr.steps[last];
  if (!(step instanceof ReplaceStep || step instanceof ReplaceAroundStep))
    return;
  let map5 = tr.mapping.maps[last], end;
  map5.forEach((_from, _to, _newFrom, newTo) => {
    if (end == null)
      end = newTo;
  });
  tr.setSelection(Selection.near(tr.doc.resolve(end), bias));
}
var UPDATED_SEL = 1;
var UPDATED_MARKS = 2;
var UPDATED_SCROLL = 4;
var Transaction = class extends Transform {
  /**
  @internal
  */
  constructor(state) {
    super(state.doc);
    this.curSelectionFor = 0;
    this.updated = 0;
    this.meta = /* @__PURE__ */ Object.create(null);
    this.time = Date.now();
    this.curSelection = state.selection;
    this.storedMarks = state.storedMarks;
  }
  /**
  The transaction's current selection. This defaults to the editor
  selection [mapped](https://prosemirror.net/docs/ref/#state.Selection.map) through the steps in the
  transaction, but can be overwritten with
  [`setSelection`](https://prosemirror.net/docs/ref/#state.Transaction.setSelection).
  */
  get selection() {
    if (this.curSelectionFor < this.steps.length) {
      this.curSelection = this.curSelection.map(this.doc, this.mapping.slice(this.curSelectionFor));
      this.curSelectionFor = this.steps.length;
    }
    return this.curSelection;
  }
  /**
  Update the transaction's current selection. Will determine the
  selection that the editor gets when the transaction is applied.
  */
  setSelection(selection) {
    if (selection.$from.doc != this.doc)
      throw new RangeError("Selection passed to setSelection must point at the current document");
    this.curSelection = selection;
    this.curSelectionFor = this.steps.length;
    this.updated = (this.updated | UPDATED_SEL) & ~UPDATED_MARKS;
    this.storedMarks = null;
    return this;
  }
  /**
  Whether the selection was explicitly updated by this transaction.
  */
  get selectionSet() {
    return (this.updated & UPDATED_SEL) > 0;
  }
  /**
  Set the current stored marks.
  */
  setStoredMarks(marks) {
    this.storedMarks = marks;
    this.updated |= UPDATED_MARKS;
    return this;
  }
  /**
  Make sure the current stored marks or, if that is null, the marks
  at the selection, match the given set of marks. Does nothing if
  this is already the case.
  */
  ensureMarks(marks) {
    if (!Mark.sameSet(this.storedMarks || this.selection.$from.marks(), marks))
      this.setStoredMarks(marks);
    return this;
  }
  /**
  Add a mark to the set of stored marks.
  */
  addStoredMark(mark) {
    return this.ensureMarks(mark.addToSet(this.storedMarks || this.selection.$head.marks()));
  }
  /**
  Remove a mark or mark type from the set of stored marks.
  */
  removeStoredMark(mark) {
    return this.ensureMarks(mark.removeFromSet(this.storedMarks || this.selection.$head.marks()));
  }
  /**
  Whether the stored marks were explicitly set for this transaction.
  */
  get storedMarksSet() {
    return (this.updated & UPDATED_MARKS) > 0;
  }
  /**
  @internal
  */
  addStep(step, doc3) {
    super.addStep(step, doc3);
    this.updated = this.updated & ~UPDATED_MARKS;
    this.storedMarks = null;
  }
  /**
  Update the timestamp for the transaction.
  */
  setTime(time) {
    this.time = time;
    return this;
  }
  /**
  Replace the current selection with the given slice.
  */
  replaceSelection(slice2) {
    this.selection.replace(this, slice2);
    return this;
  }
  /**
  Replace the selection with the given node. When `inheritMarks` is
  true and the content is inline, it inherits the marks from the
  place where it is inserted.
  */
  replaceSelectionWith(node2, inheritMarks = true) {
    let selection = this.selection;
    if (inheritMarks)
      node2 = node2.mark(this.storedMarks || (selection.empty ? selection.$from.marks() : selection.$from.marksAcross(selection.$to) || Mark.none));
    selection.replaceWith(this, node2);
    return this;
  }
  /**
  Delete the selection.
  */
  deleteSelection() {
    this.selection.replace(this);
    return this;
  }
  /**
  Replace the given range, or the selection if no range is given,
  with a text node containing the given string.
  */
  insertText(text4, from2, to) {
    let schema2 = this.doc.type.schema;
    if (from2 == null) {
      if (!text4)
        return this.deleteSelection();
      return this.replaceSelectionWith(schema2.text(text4), true);
    } else {
      if (to == null)
        to = from2;
      if (!text4)
        return this.deleteRange(from2, to);
      let marks = this.storedMarks;
      if (!marks) {
        let $from = this.doc.resolve(from2);
        marks = to == from2 ? $from.marks() : $from.marksAcross(this.doc.resolve(to));
      }
      this.replaceRangeWith(from2, to, schema2.text(text4, marks));
      if (!this.selection.empty && this.selection.to == from2 + text4.length)
        this.setSelection(Selection.near(this.selection.$to));
      return this;
    }
  }
  /**
  Store a metadata property in this transaction, keyed either by
  name or by plugin.
  */
  setMeta(key2, value) {
    this.meta[typeof key2 == "string" ? key2 : key2.key] = value;
    return this;
  }
  /**
  Retrieve a metadata property for a given name or plugin.
  */
  getMeta(key2) {
    return this.meta[typeof key2 == "string" ? key2 : key2.key];
  }
  /**
  Returns true if this transaction doesn't contain any metadata,
  and can thus safely be extended.
  */
  get isGeneric() {
    for (let _ in this.meta)
      return false;
    return true;
  }
  /**
  Indicate that the editor should scroll the selection into view
  when updated to the state produced by this transaction.
  */
  scrollIntoView() {
    this.updated |= UPDATED_SCROLL;
    return this;
  }
  /**
  True when this transaction has had `scrollIntoView` called on it.
  */
  get scrolledIntoView() {
    return (this.updated & UPDATED_SCROLL) > 0;
  }
};
function bind(f, self) {
  return !self || !f ? f : f.bind(self);
}
var FieldDesc = class {
  constructor(name, desc, self) {
    this.name = name;
    this.init = bind(desc.init, self);
    this.apply = bind(desc.apply, self);
  }
};
var baseFields = [
  new FieldDesc("doc", {
    init(config) {
      return config.doc || config.schema.topNodeType.createAndFill();
    },
    apply(tr) {
      return tr.doc;
    }
  }),
  new FieldDesc("selection", {
    init(config, instance) {
      return config.selection || Selection.atStart(instance.doc);
    },
    apply(tr) {
      return tr.selection;
    }
  }),
  new FieldDesc("storedMarks", {
    init(config) {
      return config.storedMarks || null;
    },
    apply(tr, _marks, _old, state) {
      return state.selection.$cursor ? tr.storedMarks : null;
    }
  }),
  new FieldDesc("scrollToSelection", {
    init() {
      return 0;
    },
    apply(tr, prev) {
      return tr.scrolledIntoView ? prev + 1 : prev;
    }
  })
];
var Configuration = class {
  constructor(schema2, plugins) {
    this.schema = schema2;
    this.plugins = [];
    this.pluginsByKey = /* @__PURE__ */ Object.create(null);
    this.fields = baseFields.slice();
    if (plugins)
      plugins.forEach((plugin) => {
        if (this.pluginsByKey[plugin.key])
          throw new RangeError("Adding different instances of a keyed plugin (" + plugin.key + ")");
        this.plugins.push(plugin);
        this.pluginsByKey[plugin.key] = plugin;
        if (plugin.spec.state)
          this.fields.push(new FieldDesc(plugin.key, plugin.spec.state, plugin));
      });
  }
};
var EditorState = class _EditorState {
  /**
  @internal
  */
  constructor(config) {
    this.config = config;
  }
  /**
  The schema of the state's document.
  */
  get schema() {
    return this.config.schema;
  }
  /**
  The plugins that are active in this state.
  */
  get plugins() {
    return this.config.plugins;
  }
  /**
  Apply the given transaction to produce a new state.
  */
  apply(tr) {
    return this.applyTransaction(tr).state;
  }
  /**
  @internal
  */
  filterTransaction(tr, ignore = -1) {
    for (let i2 = 0; i2 < this.config.plugins.length; i2++)
      if (i2 != ignore) {
        let plugin = this.config.plugins[i2];
        if (plugin.spec.filterTransaction && !plugin.spec.filterTransaction.call(plugin, tr, this))
          return false;
      }
    return true;
  }
  /**
  Verbose variant of [`apply`](https://prosemirror.net/docs/ref/#state.EditorState.apply) that
  returns the precise transactions that were applied (which might
  be influenced by the [transaction
  hooks](https://prosemirror.net/docs/ref/#state.PluginSpec.filterTransaction) of
  plugins) along with the new state.
  */
  applyTransaction(rootTr) {
    if (!this.filterTransaction(rootTr))
      return { state: this, transactions: [] };
    let trs = [rootTr], newState = this.applyInner(rootTr), seen = null;
    for (; ; ) {
      let haveNew = false;
      for (let i2 = 0; i2 < this.config.plugins.length; i2++) {
        let plugin = this.config.plugins[i2];
        if (plugin.spec.appendTransaction) {
          let n = seen ? seen[i2].n : 0, oldState = seen ? seen[i2].state : this;
          let tr = n < trs.length && plugin.spec.appendTransaction.call(plugin, n ? trs.slice(n) : trs, oldState, newState);
          if (tr && newState.filterTransaction(tr, i2)) {
            tr.setMeta("appendedTransaction", rootTr);
            if (!seen) {
              seen = [];
              for (let j = 0; j < this.config.plugins.length; j++)
                seen.push(j < i2 ? { state: newState, n: trs.length } : { state: this, n: 0 });
            }
            trs.push(tr);
            newState = newState.applyInner(tr);
            haveNew = true;
          }
          if (seen)
            seen[i2] = { state: newState, n: trs.length };
        }
      }
      if (!haveNew)
        return { state: newState, transactions: trs };
    }
  }
  /**
  @internal
  */
  applyInner(tr) {
    if (!tr.before.eq(this.doc))
      throw new RangeError("Applying a mismatched transaction");
    let newInstance = new _EditorState(this.config), fields = this.config.fields;
    for (let i2 = 0; i2 < fields.length; i2++) {
      let field = fields[i2];
      newInstance[field.name] = field.apply(tr, this[field.name], this, newInstance);
    }
    return newInstance;
  }
  /**
  Accessor that constructs and returns a new [transaction](https://prosemirror.net/docs/ref/#state.Transaction) from this state.
  */
  get tr() {
    return new Transaction(this);
  }
  /**
  Create a new state.
  */
  static create(config) {
    let $config = new Configuration(config.doc ? config.doc.type.schema : config.schema, config.plugins);
    let instance = new _EditorState($config);
    for (let i2 = 0; i2 < $config.fields.length; i2++)
      instance[$config.fields[i2].name] = $config.fields[i2].init(config, instance);
    return instance;
  }
  /**
  Create a new state based on this one, but with an adjusted set
  of active plugins. State fields that exist in both sets of
  plugins are kept unchanged. Those that no longer exist are
  dropped, and those that are new are initialized using their
  [`init`](https://prosemirror.net/docs/ref/#state.StateField.init) method, passing in the new
  configuration object..
  */
  reconfigure(config) {
    let $config = new Configuration(this.schema, config.plugins);
    let fields = $config.fields, instance = new _EditorState($config);
    for (let i2 = 0; i2 < fields.length; i2++) {
      let name = fields[i2].name;
      instance[name] = this.hasOwnProperty(name) ? this[name] : fields[i2].init(config, instance);
    }
    return instance;
  }
  /**
  Serialize this state to JSON. If you want to serialize the state
  of plugins, pass an object mapping property names to use in the
  resulting JSON object to plugin objects. The argument may also be
  a string or number, in which case it is ignored, to support the
  way `JSON.stringify` calls `toString` methods.
  */
  toJSON(pluginFields) {
    let result = { doc: this.doc.toJSON(), selection: this.selection.toJSON() };
    if (this.storedMarks)
      result.storedMarks = this.storedMarks.map((m) => m.toJSON());
    if (pluginFields && typeof pluginFields == "object")
      for (let prop in pluginFields) {
        if (prop == "doc" || prop == "selection")
          throw new RangeError("The JSON fields `doc` and `selection` are reserved");
        let plugin = pluginFields[prop], state = plugin.spec.state;
        if (state && state.toJSON)
          result[prop] = state.toJSON.call(plugin, this[plugin.key]);
      }
    return result;
  }
  /**
  Deserialize a JSON representation of a state. `config` should
  have at least a `schema` field, and should contain array of
  plugins to initialize the state with. `pluginFields` can be used
  to deserialize the state of plugins, by associating plugin
  instances with the property names they use in the JSON object.
  */
  static fromJSON(config, json, pluginFields) {
    if (!json)
      throw new RangeError("Invalid input for EditorState.fromJSON");
    if (!config.schema)
      throw new RangeError("Required config field 'schema' missing");
    let $config = new Configuration(config.schema, config.plugins);
    let instance = new _EditorState($config);
    $config.fields.forEach((field) => {
      if (field.name == "doc") {
        instance.doc = Node.fromJSON(config.schema, json.doc);
      } else if (field.name == "selection") {
        instance.selection = Selection.fromJSON(instance.doc, json.selection);
      } else if (field.name == "storedMarks") {
        if (json.storedMarks)
          instance.storedMarks = json.storedMarks.map(config.schema.markFromJSON);
      } else {
        if (pluginFields)
          for (let prop in pluginFields) {
            let plugin = pluginFields[prop], state = plugin.spec.state;
            if (plugin.key == field.name && state && state.fromJSON && Object.prototype.hasOwnProperty.call(json, prop)) {
              instance[field.name] = state.fromJSON.call(plugin, config, json[prop], instance);
              return;
            }
          }
        instance[field.name] = field.init(config, instance);
      }
    });
    return instance;
  }
};
function bindProps(obj, self, target) {
  for (let prop in obj) {
    let val = obj[prop];
    if (val instanceof Function)
      val = val.bind(self);
    else if (prop == "handleDOMEvents")
      val = bindProps(val, self, {});
    target[prop] = val;
  }
  return target;
}
var Plugin = class {
  /**
  Create a plugin.
  */
  constructor(spec) {
    this.spec = spec;
    this.props = {};
    if (spec.props)
      bindProps(spec.props, this, this.props);
    this.key = spec.key ? spec.key.key : createKey("plugin");
  }
  /**
  Extract the plugin's state field from an editor state.
  */
  getState(state) {
    return state[this.key];
  }
};
var keys = /* @__PURE__ */ Object.create(null);
function createKey(name) {
  if (name in keys)
    return name + "$" + ++keys[name];
  keys[name] = 0;
  return name + "$";
}
var PluginKey = class {
  /**
  Create a plugin key.
  */
  constructor(name = "key") {
    this.key = createKey(name);
  }
  /**
  Get the active plugin with this key, if any, from an editor
  state.
  */
  get(state) {
    return state.config.pluginsByKey[this.key];
  }
  /**
  Get the plugin's state from an editor state.
  */
  getState(state) {
    return state[this.key];
  }
};

// node_modules/.pnpm/prosemirror-view@1.42.8/node_modules/prosemirror-view/dist/index.js
var domIndex = function(node2) {
  for (var index2 = 0; ; index2++) {
    node2 = node2.previousSibling;
    if (!node2)
      return index2;
  }
};
var parentNode = function(node2) {
  let parent = node2.assignedSlot || node2.parentNode;
  return parent && parent.nodeType == 11 ? parent.host : parent;
};
var reusedRange = null;
var textRange = function(node2, from2, to) {
  let range = reusedRange || (reusedRange = document.createRange());
  range.setEnd(node2, to == null ? node2.nodeValue.length : to);
  range.setStart(node2, from2 || 0);
  return range;
};
var clearReusedRange = function() {
  reusedRange = null;
};
var isEquivalentPosition = function(node2, off, targetNode, targetOff) {
  return targetNode && (scanFor(node2, off, targetNode, targetOff, -1) || scanFor(node2, off, targetNode, targetOff, 1));
};
var atomElements = /^(img|br|input|textarea|hr)$/i;
function scanFor(node2, off, targetNode, targetOff, dir) {
  var _a;
  for (; ; ) {
    if (node2 == targetNode && off == targetOff)
      return true;
    if (off == (dir < 0 ? 0 : nodeSize(node2))) {
      let parent = node2.parentNode;
      if (!parent || !isElt(parent) || hasBlockDesc(node2) || atomElements.test(node2.nodeName) || node2.contentEditable == "false")
        return false;
      off = domIndex(node2) + (dir < 0 ? 0 : 1);
      node2 = parent;
    } else if (isElt(node2)) {
      let child = node2.childNodes[off + (dir < 0 ? -1 : 0)];
      if (isElt(child) && child.contentEditable == "false") {
        if ((_a = child.pmViewDesc) === null || _a === void 0 ? void 0 : _a.ignoreForSelection)
          off += dir;
        else
          return false;
      } else {
        node2 = child;
        off = dir < 0 ? nodeSize(node2) : 0;
      }
    } else {
      return false;
    }
  }
}
function nodeSize(node2) {
  return node2.nodeType == 3 ? node2.nodeValue.length : node2.childNodes.length;
}
function isElt(node2) {
  return node2.nodeType == 1;
}
function isText(node2) {
  return node2.nodeType == 3;
}
function contains(parent, child) {
  return child ? parent.contains(isElt(child) ? child : child.parentNode) : false;
}
function textNodeBefore$1(node2, offset) {
  for (; ; ) {
    if (isText(node2) && offset)
      return node2;
    if (isElt(node2) && offset > 0) {
      if (node2.contentEditable == "false")
        return null;
      node2 = node2.childNodes[offset - 1];
      offset = nodeSize(node2);
    } else if (node2.parentNode && !hasBlockDesc(node2)) {
      offset = domIndex(node2);
      node2 = node2.parentNode;
    } else {
      return null;
    }
  }
}
function textNodeAfter$1(node2, offset) {
  for (; ; ) {
    if (isText(node2) && offset < node2.nodeValue.length)
      return node2;
    if (isElt(node2) && offset < node2.childNodes.length) {
      if (node2.contentEditable == "false")
        return null;
      node2 = node2.childNodes[offset];
      offset = 0;
    } else if (node2.parentNode && !hasBlockDesc(node2)) {
      offset = domIndex(node2) + 1;
      node2 = node2.parentNode;
    } else {
      return null;
    }
  }
}
function isOnEdge(node2, offset, parent) {
  for (let atStart = offset == 0, atEnd = offset == nodeSize(node2); atStart || atEnd; ) {
    if (node2 == parent)
      return true;
    let index2 = domIndex(node2);
    node2 = node2.parentNode;
    if (!node2)
      return false;
    atStart = atStart && index2 == 0;
    atEnd = atEnd && index2 == nodeSize(node2);
  }
}
function hasBlockDesc(dom) {
  let desc;
  for (let cur = dom; cur; cur = cur.parentNode)
    if (desc = cur.pmViewDesc)
      break;
  return desc && desc.node && desc.node.isBlock && (desc.dom == dom || desc.contentDOM == dom);
}
var selectionCollapsed = function(domSel) {
  return domSel.focusNode && isEquivalentPosition(domSel.focusNode, domSel.focusOffset, domSel.anchorNode, domSel.anchorOffset);
};
function keyEvent(keyCode, key2) {
  let event = document.createEvent("Event");
  event.initEvent("keydown", true, true);
  event.keyCode = keyCode;
  event.key = event.code = key2;
  return event;
}
function deepActiveElement(doc3) {
  let elt = doc3.activeElement;
  while (elt && elt.shadowRoot)
    elt = elt.shadowRoot.activeElement;
  return elt;
}
function caretFromPoint(doc3, x, y) {
  if (doc3.caretPositionFromPoint) {
    try {
      let pos = doc3.caretPositionFromPoint(x, y);
      if (pos)
        return { node: pos.offsetNode, offset: Math.min(nodeSize(pos.offsetNode), pos.offset) };
    } catch (_) {
    }
  }
  if (doc3.caretRangeFromPoint) {
    let range = doc3.caretRangeFromPoint(x, y);
    if (range)
      return { node: range.startContainer, offset: Math.min(nodeSize(range.startContainer), range.startOffset) };
  }
}
var nav = typeof navigator != "undefined" ? navigator : null;
var doc2 = typeof document != "undefined" ? document : null;
var agent = nav && nav.userAgent || "";
var ie_edge = /Edge\/(\d+)/.exec(agent);
var ie_upto10 = /MSIE \d/.exec(agent);
var ie_11up = /Trident\/(?:[7-9]|\d{2,})\..*rv:(\d+)/.exec(agent);
var ie = !!(ie_upto10 || ie_11up || ie_edge);
var ie_version = ie_upto10 ? document.documentMode : ie_11up ? +ie_11up[1] : ie_edge ? +ie_edge[1] : 0;
var gecko = !ie && /gecko\/(\d+)/i.test(agent);
gecko && +(/Firefox\/(\d+)/.exec(agent) || [0, 0])[1];
var _chrome = !ie && /Chrome\/(\d+)/.exec(agent);
var chrome = !!_chrome;
var chrome_version = _chrome ? +_chrome[1] : 0;
var safari = !ie && !!nav && /Apple Computer/.test(nav.vendor);
var ios = safari && (/Mobile\/\w+/.test(agent) || !!nav && nav.maxTouchPoints > 2);
var mac = ios || (nav ? /Mac/.test(nav.platform) : false);
var windows = nav ? /Win/.test(nav.platform) : false;
var android = /Android \d/.test(agent);
var webkit = !!doc2 && "webkitFontSmoothing" in doc2.documentElement.style;
var webkit_version = webkit ? +(/\bAppleWebKit\/(\d+)/.exec(navigator.userAgent) || [0, 0])[1] : 0;
function windowRect(doc3) {
  let vp = doc3.defaultView && doc3.defaultView.visualViewport;
  if (vp)
    return {
      left: 0,
      right: vp.width,
      top: 0,
      bottom: vp.height
    };
  return {
    left: 0,
    right: doc3.documentElement.clientWidth,
    top: 0,
    bottom: doc3.documentElement.clientHeight
  };
}
function getSide(value, side) {
  return typeof value == "number" ? value : value[side];
}
function clientRect(node2) {
  let rect = node2.getBoundingClientRect();
  let scaleX = rect.width / node2.offsetWidth || 1;
  let scaleY = rect.height / node2.offsetHeight || 1;
  return {
    left: rect.left,
    right: rect.left + node2.clientWidth * scaleX,
    top: rect.top,
    bottom: rect.top + node2.clientHeight * scaleY
  };
}
function scrollRectIntoView(view, rect, startDOM) {
  if (!nonZero(rect) && rect.left == 0)
    return;
  let scrollThreshold = view.someProp("scrollThreshold") || 0, scrollMargin = view.someProp("scrollMargin") || 5;
  let doc3 = view.dom.ownerDocument;
  for (let parent = startDOM || view.dom; ; ) {
    if (!parent)
      break;
    if (!isElt(parent)) {
      parent = parentNode(parent);
      continue;
    }
    let atTop = parent == doc3.body;
    let bounding = atTop ? windowRect(doc3) : clientRect(parent);
    let moveX = 0, moveY = 0;
    if (rect.top < bounding.top + getSide(scrollThreshold, "top"))
      moveY = -(bounding.top - rect.top + getSide(scrollMargin, "top"));
    else if (rect.bottom > bounding.bottom - getSide(scrollThreshold, "bottom"))
      moveY = rect.bottom - rect.top > bounding.bottom - bounding.top ? rect.top + getSide(scrollMargin, "top") - bounding.top : rect.bottom - bounding.bottom + getSide(scrollMargin, "bottom");
    if (rect.left < bounding.left + getSide(scrollThreshold, "left"))
      moveX = -(bounding.left - rect.left + getSide(scrollMargin, "left"));
    else if (rect.right > bounding.right - getSide(scrollThreshold, "right"))
      moveX = rect.right - bounding.right + getSide(scrollMargin, "right");
    if (moveX || moveY) {
      if (atTop) {
        doc3.defaultView.scrollBy(moveX, moveY);
      } else {
        let startX = parent.scrollLeft, startY = parent.scrollTop;
        if (moveY)
          parent.scrollTop += moveY;
        if (moveX)
          parent.scrollLeft += moveX;
        let dX = parent.scrollLeft - startX, dY = parent.scrollTop - startY;
        rect = { left: rect.left - dX, top: rect.top - dY, right: rect.right - dX, bottom: rect.bottom - dY };
      }
    }
    let pos = atTop ? "fixed" : getComputedStyle(parent).position;
    if (/^(fixed|sticky)$/.test(pos))
      break;
    parent = pos == "absolute" ? parent.offsetParent : parentNode(parent);
  }
}
function storeScrollPos(view) {
  let rect = view.dom.getBoundingClientRect(), startY = Math.max(0, rect.top);
  let refDOM, refTop;
  for (let x = (rect.left + rect.right) / 2, y = startY + 1; y < Math.min(innerHeight, rect.bottom); y += 5) {
    let dom = view.root.elementFromPoint(x, y);
    if (!dom || dom == view.dom || !view.dom.contains(dom))
      continue;
    let localRect = dom.getBoundingClientRect();
    if (localRect.top >= startY - 20) {
      refDOM = dom;
      refTop = localRect.top;
      break;
    }
  }
  return { refDOM, refTop, stack: scrollStack(view.dom) };
}
function scrollStack(dom) {
  let stack = [], doc3 = dom.ownerDocument;
  for (let cur = dom; cur; cur = parentNode(cur)) {
    stack.push({ dom: cur, top: cur.scrollTop, left: cur.scrollLeft });
    if (dom == doc3)
      break;
  }
  return stack;
}
function resetScrollPos({ refDOM, refTop, stack }) {
  let newRefTop = refDOM ? refDOM.getBoundingClientRect().top : 0;
  restoreScrollStack(stack, newRefTop == 0 ? 0 : newRefTop - refTop);
}
function restoreScrollStack(stack, dTop) {
  for (let i2 = 0; i2 < stack.length; i2++) {
    let { dom, top, left } = stack[i2];
    if (dom.scrollTop != top + dTop)
      dom.scrollTop = top + dTop;
    if (dom.scrollLeft != left)
      dom.scrollLeft = left;
  }
}
var preventScrollSupported = null;
function focusPreventScroll(dom) {
  if (dom.setActive)
    return dom.setActive();
  if (preventScrollSupported)
    return dom.focus(preventScrollSupported);
  let stored = scrollStack(dom);
  dom.focus(preventScrollSupported == null ? {
    get preventScroll() {
      preventScrollSupported = { preventScroll: true };
      return true;
    }
  } : void 0);
  if (!preventScrollSupported) {
    preventScrollSupported = false;
    restoreScrollStack(stored, 0);
  }
}
function findOffsetInNode(node2, coords) {
  let closest;
  let dxClosest = 2e8, coordsClosest, offset = 0;
  let rowBot = coords.top, rowTop = coords.top;
  let firstBelow, coordsBelow;
  for (let child = node2.firstChild, childIndex = 0; child; child = child.nextSibling, childIndex++) {
    let rects;
    if (isElt(child))
      rects = child.getClientRects();
    else if (isText(child))
      rects = textRange(child).getClientRects();
    else
      continue;
    for (let i2 = 0; i2 < rects.length; i2++) {
      let rect = rects[i2];
      if (rect.top <= rowBot && rect.bottom >= rowTop) {
        rowBot = Math.max(rect.bottom, rowBot);
        rowTop = Math.min(rect.top, rowTop);
        let dx = rect.left > coords.left ? rect.left - coords.left : rect.right < coords.left ? coords.left - rect.right : 0;
        if (dx < dxClosest) {
          closest = child;
          dxClosest = dx;
          coordsClosest = dx && isText(closest) ? {
            left: rect.right < coords.left ? rect.right : rect.left,
            top: coords.top
          } : coords;
          if (isElt(child) && dx)
            offset = childIndex + (coords.left >= (rect.left + rect.right) / 2 ? 1 : 0);
          continue;
        }
      } else if (rect.top > coords.top && !firstBelow && rect.left <= coords.left && rect.right >= coords.left) {
        firstBelow = child;
        coordsBelow = { left: Math.max(rect.left, Math.min(rect.right, coords.left)), top: rect.top };
      }
      if (!closest && (coords.left >= rect.right && coords.top >= rect.top || coords.left >= rect.left && coords.top >= rect.bottom))
        offset = childIndex + 1;
    }
  }
  if (!closest && firstBelow) {
    closest = firstBelow;
    coordsClosest = coordsBelow;
    dxClosest = 0;
  }
  if (closest && isText(closest))
    return findOffsetInText(closest, coordsClosest);
  if (!closest || dxClosest)
    return { node: node2, offset };
  return findOffsetInNode(closest, coordsClosest);
}
function findOffsetInText(node2, coords) {
  let len = node2.nodeValue.length;
  let range = document.createRange(), result;
  for (let i2 = 0; i2 < len; i2++) {
    range.setEnd(node2, i2 + 1);
    range.setStart(node2, i2);
    let rect = singleRect(range, 1);
    if (rect.top == rect.bottom)
      continue;
    if (inRect(coords, rect)) {
      result = { node: node2, offset: i2 + (coords.left >= (rect.left + rect.right) / 2 ? 1 : 0) };
      break;
    }
  }
  range.detach();
  return result || { node: node2, offset: 0 };
}
function inRect(coords, rect) {
  return coords.left >= rect.left - 1 && coords.left <= rect.right + 1 && coords.top >= rect.top - 1 && coords.top <= rect.bottom + 1;
}
function targetKludge(dom, coords) {
  let parent = dom.parentNode;
  if (parent && /^li$/i.test(parent.nodeName) && coords.left < dom.getBoundingClientRect().left)
    return parent;
  return dom;
}
function posFromElement(view, elt, coords) {
  let { node: node2, offset } = findOffsetInNode(elt, coords), bias = -1;
  if (isElt(node2) && !node2.firstChild) {
    let rect = node2.getBoundingClientRect();
    bias = rect.left != rect.right && coords.left > (rect.left + rect.right) / 2 ? 1 : -1;
  }
  return view.docView.posFromDOM(node2, offset, bias);
}
function posFromCaret(view, node2, offset, coords) {
  let outsideBlock = -1;
  for (let cur = node2, sawBlock = false; ; ) {
    if (cur == view.dom)
      break;
    let desc = view.docView.nearestDesc(cur, true), rect;
    if (!desc)
      return null;
    if (isElt(desc.dom) && (desc.node.isBlock && desc.parent || !desc.contentDOM) && // Ignore elements with zero-size bounding rectangles
    ((rect = desc.dom.getBoundingClientRect()).width || rect.height)) {
      if (desc.node.isBlock && desc.parent && !/^T(R|BODY|HEAD|FOOT)$/.test(desc.dom.nodeName)) {
        if (!sawBlock && rect.left > coords.left || rect.top > coords.top)
          outsideBlock = desc.posBefore;
        else if (!sawBlock && rect.right < coords.left || rect.bottom < coords.top)
          outsideBlock = desc.posAfter;
        sawBlock = true;
      }
      if (!desc.contentDOM && outsideBlock < 0 && !desc.node.isText) {
        let before = desc.node.isBlock ? coords.top < (rect.top + rect.bottom) / 2 : coords.left < (rect.left + rect.right) / 2;
        return before ? desc.posBefore : desc.posAfter;
      }
    }
    cur = desc.dom.parentNode;
  }
  return outsideBlock > -1 ? outsideBlock : view.docView.posFromDOM(node2, offset, -1);
}
function elementFromPoint(element, coords, box) {
  let len = element.childNodes.length;
  if (len && box.top < box.bottom) {
    for (let startI = Math.max(0, Math.min(len - 1, Math.floor(len * (coords.top - box.top) / (box.bottom - box.top)) - 2)), i2 = startI; ; ) {
      let child = element.childNodes[i2];
      if (isElt(child)) {
        let rects = child.getClientRects();
        for (let j = 0; j < rects.length; j++) {
          let rect = rects[j];
          if (inRect(coords, rect))
            return elementFromPoint(child, coords, rect);
        }
      }
      if ((i2 = (i2 + 1) % len) == startI)
        break;
    }
  }
  return element;
}
function posAtCoords(view, coords) {
  let doc3 = view.dom.ownerDocument, node2, offset = 0;
  let caret = caretFromPoint(doc3, coords.left, coords.top);
  if (caret)
    ({ node: node2, offset } = caret);
  let elt = (view.root.elementFromPoint ? view.root : doc3).elementFromPoint(coords.left, coords.top);
  let pos;
  if (!elt || !view.dom.contains(elt)) {
    let box = view.dom.getBoundingClientRect();
    if (!inRect(coords, box))
      return null;
    elt = elementFromPoint(view.dom, coords, box);
    if (!elt)
      return null;
  }
  if (safari) {
    for (let p = elt; node2 && p; p = parentNode(p))
      if (p.draggable)
        node2 = void 0;
  }
  elt = targetKludge(elt, coords);
  if (node2) {
    if (gecko && isElt(node2)) {
      offset = Math.min(offset, node2.childNodes.length);
      if (offset < node2.childNodes.length) {
        let next = node2.childNodes[offset], box;
        if (next.nodeName == "IMG" && (box = next.getBoundingClientRect()).right <= coords.left && box.bottom > coords.top)
          offset++;
      }
    }
    let prev;
    if (webkit && offset && isElt(node2) && isElt(prev = node2.childNodes[offset - 1]) && prev.contentEditable == "false" && prev.getBoundingClientRect().top >= coords.top)
      offset--;
    if (node2 == view.dom && offset == node2.childNodes.length - 1 && isElt(node2.lastChild) && coords.top > node2.lastChild.getBoundingClientRect().bottom)
      pos = view.state.doc.content.size;
    else if (offset == 0 || !isElt(node2) || node2.childNodes[offset - 1].nodeName != "BR")
      pos = posFromCaret(view, node2, offset, coords);
  }
  if (pos == null)
    pos = posFromElement(view, elt, coords);
  let desc = view.docView.nearestDesc(elt, true);
  return { pos, inside: desc ? desc.posAtStart - desc.border : -1 };
}
function nonZero(rect) {
  return rect.top < rect.bottom || rect.left < rect.right;
}
function singleRect(target, bias) {
  let rects = target.getClientRects();
  if (rects.length) {
    let first = rects[bias < 0 ? 0 : rects.length - 1];
    if (nonZero(first))
      return first;
  }
  return Array.prototype.find.call(rects, nonZero) || target.getBoundingClientRect();
}
var BIDI = /[\u0590-\u05f4\u0600-\u06ff\u0700-\u08ac]/;
function coordsAtPos(view, pos, side) {
  let { node: node2, offset, atom } = view.docView.domFromPos(pos, side < 0 ? -1 : 1);
  let supportEmptyRange = webkit || gecko;
  if (isText(node2)) {
    if (supportEmptyRange && (BIDI.test(node2.nodeValue) || (side < 0 ? !offset : offset == node2.nodeValue.length))) {
      let rect = singleRect(textRange(node2, offset, offset), side);
      if (gecko && offset && /\s/.test(node2.nodeValue[offset - 1]) && offset < node2.nodeValue.length) {
        let rectBefore = singleRect(textRange(node2, offset - 1, offset - 1), -1);
        if (rectBefore.top == rect.top) {
          let rectAfter = singleRect(textRange(node2, offset, offset + 1), -1);
          if (rectAfter.top != rect.top)
            return flattenV(rectAfter, rectAfter.left < rectBefore.left);
        }
      }
      return rect;
    } else {
      let from2 = offset, to = offset, takeSide = side < 0 ? 1 : -1;
      if (side < 0 && !offset) {
        to++;
        takeSide = -1;
      } else if (side >= 0 && offset == node2.nodeValue.length) {
        from2--;
        takeSide = 1;
      } else if (side < 0) {
        from2--;
      } else {
        to++;
      }
      return flattenV(singleRect(textRange(node2, from2, to), takeSide), takeSide < 0);
    }
  }
  let $dom = view.state.doc.resolve(pos - (atom || 0));
  if (!$dom.parent.inlineContent) {
    if (atom == null && offset && (side < 0 || offset == nodeSize(node2))) {
      let before = node2.childNodes[offset - 1];
      if (isElt(before))
        return flattenH(before.getBoundingClientRect(), false);
    }
    if (atom == null && offset < nodeSize(node2)) {
      let after = node2.childNodes[offset];
      if (isElt(after))
        return flattenH(after.getBoundingClientRect(), true);
    }
    return flattenH(node2.getBoundingClientRect(), side >= 0);
  }
  if (atom == null && offset && (side < 0 || offset == nodeSize(node2))) {
    let before = node2.childNodes[offset - 1];
    let target = isText(before) ? textRange(before, nodeSize(before) - (supportEmptyRange ? 0 : 1)) : isElt(before) && (before.nodeName != "BR" || !before.nextSibling) ? before : null;
    if (target)
      return flattenV(singleRect(target, 1), false);
  }
  if (atom == null && offset < nodeSize(node2)) {
    let after = node2.childNodes[offset];
    while (after.pmViewDesc && after.pmViewDesc.ignoreForCoords)
      after = after.nextSibling;
    let target = !after ? null : isText(after) ? textRange(after, 0, supportEmptyRange ? 0 : 1) : isElt(after) ? after : null;
    if (target)
      return flattenV(singleRect(target, -1), true);
  }
  return flattenV(singleRect(isText(node2) ? textRange(node2) : node2, -side), side >= 0);
}
function flattenV(rect, left) {
  if (rect.width == 0)
    return rect;
  let x = left ? rect.left : rect.right;
  return { top: rect.top, bottom: rect.bottom, left: x, right: x };
}
function flattenH(rect, top) {
  if (rect.height == 0)
    return rect;
  let y = top ? rect.top : rect.bottom;
  return { top: y, bottom: y, left: rect.left, right: rect.right };
}
function withFlushedState(view, state, f) {
  let viewState = view.state, active = view.root.activeElement;
  if (viewState != state)
    view.updateState(state);
  if (active != view.dom)
    view.focus();
  try {
    return f();
  } finally {
    if (viewState != state)
      view.updateState(viewState);
    if (active != view.dom && active)
      active.focus();
  }
}
function endOfTextblockVertical(view, state, dir) {
  let sel = state.selection;
  let $pos = dir == "up" ? sel.$from : sel.$to;
  return withFlushedState(view, state, () => {
    let { node: dom } = view.docView.domFromPos($pos.pos, dir == "up" ? -1 : 1);
    for (; ; ) {
      let nearest = view.docView.nearestDesc(dom, true);
      if (!nearest)
        break;
      if (nearest.node.isBlock) {
        dom = nearest.contentDOM || nearest.dom;
        break;
      }
      dom = nearest.dom.parentNode;
    }
    let coords = coordsAtPos(view, $pos.pos, 1);
    for (let child = dom.firstChild; child; child = child.nextSibling) {
      let boxes;
      if (isElt(child))
        boxes = child.getClientRects();
      else if (isText(child))
        boxes = textRange(child, 0, child.nodeValue.length).getClientRects();
      else
        continue;
      for (let i2 = 0; i2 < boxes.length; i2++) {
        let box = boxes[i2];
        if (box.bottom > box.top + 1 && (dir == "up" ? coords.top - box.top > (box.bottom - coords.top) * 2 : box.bottom - coords.bottom > (coords.bottom - box.top) * 2))
          return false;
      }
    }
    return true;
  });
}
var maybeRTL = /[\u0590-\u08ac]/;
function endOfTextblockHorizontal(view, state, dir) {
  let { $head } = state.selection;
  if (!$head.parent.isTextblock)
    return false;
  let offset = $head.parentOffset, atStart = !offset, atEnd = offset == $head.parent.content.size;
  let sel = view.domSelection();
  if (!sel)
    return $head.pos == $head.start() || $head.pos == $head.end();
  if (!maybeRTL.test($head.parent.textContent) || !sel.modify)
    return dir == "left" || dir == "backward" ? atStart : atEnd;
  return withFlushedState(view, state, () => {
    let { focusNode: oldNode, focusOffset: oldOff, anchorNode, anchorOffset } = view.domSelectionRange();
    let oldBidiLevel = sel.caretBidiLevel;
    sel.modify("move", dir, "character");
    let parentDOM = $head.depth ? view.docView.domAfterPos($head.before()) : view.dom;
    let { focusNode: newNode, focusOffset: newOff } = view.domSelectionRange();
    let result = newNode && !contains(parentDOM, newNode) || oldNode == newNode && oldOff == newOff;
    try {
      sel.collapse(anchorNode, anchorOffset);
      if (oldNode && (oldNode != anchorNode || oldOff != anchorOffset) && sel.extend)
        sel.extend(oldNode, oldOff);
    } catch (_) {
    }
    if (oldBidiLevel != null)
      sel.caretBidiLevel = oldBidiLevel;
    return result;
  });
}
var cachedState = null;
var cachedDir = null;
var cachedResult = false;
function endOfTextblock(view, state, dir) {
  if (cachedState == state && cachedDir == dir)
    return cachedResult;
  cachedState = state;
  cachedDir = dir;
  return cachedResult = dir == "up" || dir == "down" ? endOfTextblockVertical(view, state, dir) : endOfTextblockHorizontal(view, state, dir);
}
var NOT_DIRTY = 0;
var CHILD_DIRTY = 1;
var CONTENT_DIRTY = 2;
var NODE_DIRTY = 3;
var ViewDesc = class {
  constructor(parent, children, dom, contentDOM) {
    this.parent = parent;
    this.children = children;
    this.dom = dom;
    this.contentDOM = contentDOM;
    this.dirty = NOT_DIRTY;
    dom.pmViewDesc = this;
  }
  // Used to check whether a given description corresponds to a
  // widget/mark/node.
  matchesWidget(widget) {
    return false;
  }
  matchesMark(mark) {
    return false;
  }
  matchesNode(node2, outerDeco, innerDeco) {
    return false;
  }
  matchesHack(nodeName) {
    return false;
  }
  // When parsing in-editor content (in domchange.js), we allow
  // descriptions to determine the parse rules that should be used to
  // parse them.
  parseRule(addedNodes) {
    return null;
  }
  // Used by the editor's event handler to ignore events that come
  // from certain descs.
  stopEvent(event) {
    return false;
  }
  // The size of the content represented by this desc.
  get size() {
    let size = 0;
    for (let i2 = 0; i2 < this.children.length; i2++)
      size += this.children[i2].size;
    return size;
  }
  // For block nodes, this represents the space taken up by their
  // start/end tokens.
  get border() {
    return 0;
  }
  destroy() {
    this.parent = void 0;
    if (this.dom.pmViewDesc == this)
      this.dom.pmViewDesc = void 0;
    for (let i2 = 0; i2 < this.children.length; i2++)
      this.children[i2].destroy();
  }
  posBeforeChild(child) {
    for (let i2 = 0, pos = this.posAtStart; ; i2++) {
      let cur = this.children[i2];
      if (cur == child)
        return pos;
      pos += cur.size;
    }
  }
  get posBefore() {
    return this.parent.posBeforeChild(this);
  }
  get posAtStart() {
    return this.parent ? this.parent.posBeforeChild(this) + this.border : 0;
  }
  get posAfter() {
    return this.posBefore + this.size;
  }
  get posAtEnd() {
    return this.posAtStart + this.size - 2 * this.border;
  }
  localPosFromDOM(dom, offset, bias) {
    if (this.contentDOM && contains(this.contentDOM, dom)) {
      if (bias < 0) {
        let domBefore, desc;
        if (dom == this.contentDOM) {
          domBefore = dom.childNodes[offset - 1];
        } else {
          while (dom.parentNode != this.contentDOM)
            dom = dom.parentNode;
          domBefore = dom.previousSibling;
        }
        while (domBefore && !((desc = domBefore.pmViewDesc) && desc.parent == this))
          domBefore = domBefore.previousSibling;
        return domBefore ? this.posBeforeChild(desc) + desc.size : this.posAtStart;
      } else {
        let domAfter, desc;
        if (dom == this.contentDOM) {
          domAfter = dom.childNodes[offset];
        } else {
          while (dom.parentNode != this.contentDOM)
            dom = dom.parentNode;
          domAfter = dom.nextSibling;
        }
        while (domAfter && !((desc = domAfter.pmViewDesc) && desc.parent == this))
          domAfter = domAfter.nextSibling;
        return domAfter ? this.posBeforeChild(desc) : this.posAtEnd;
      }
    }
    let atEnd;
    if (dom == this.dom && this.contentDOM) {
      atEnd = offset > domIndex(this.contentDOM);
    } else if (this.contentDOM && this.contentDOM != this.dom && this.dom.contains(this.contentDOM)) {
      let rel = dom.compareDocumentPosition(this.contentDOM);
      if (rel & 16) {
        atEnd = offset > Array.from(dom.childNodes).findIndex((n) => n.contains(this.contentDOM));
      } else {
        atEnd = !(rel & 4);
      }
    } else if (this.dom.firstChild) {
      if (offset == 0)
        for (let search2 = dom; ; search2 = search2.parentNode) {
          if (search2 == this.dom) {
            atEnd = false;
            break;
          }
          if (search2.previousSibling)
            break;
        }
      if (atEnd == null && offset == dom.childNodes.length)
        for (let search2 = dom; ; search2 = search2.parentNode) {
          if (search2 == this.dom) {
            atEnd = true;
            break;
          }
          if (search2.nextSibling)
            break;
        }
    }
    return (atEnd == null ? bias > 0 : atEnd) ? this.posAtEnd : this.posAtStart;
  }
  nearestDesc(dom, onlyNodes = false) {
    for (let first = true, cur = dom; cur; cur = cur.parentNode) {
      let desc = this.getDesc(cur), nodeDOM;
      if (desc && (!onlyNodes || desc.node)) {
        if (first && (nodeDOM = desc.nodeDOM) && !(isElt(nodeDOM) ? contains(nodeDOM, dom) : nodeDOM == dom))
          first = false;
        else
          return desc;
      }
    }
  }
  getDesc(dom) {
    let desc = dom.pmViewDesc;
    for (let cur = desc; cur; cur = cur.parent)
      if (cur == this)
        return desc;
  }
  posFromDOM(dom, offset, bias) {
    for (let scan = dom; scan; scan = scan.parentNode) {
      let desc = this.getDesc(scan);
      if (desc)
        return desc.localPosFromDOM(dom, offset, bias);
    }
    return -1;
  }
  // Find the desc for the node after the given pos, if any. (When a
  // parent node overrode rendering, there might not be one.)
  descAt(pos) {
    for (let i2 = 0, offset = 0; i2 < this.children.length; i2++) {
      let child = this.children[i2], end = offset + child.size;
      if (offset == pos && end != offset) {
        while (!child.border && child.children.length) {
          for (let i3 = 0; i3 < child.children.length; i3++) {
            let inner = child.children[i3];
            if (inner.size) {
              child = inner;
              break;
            }
          }
        }
        return child;
      }
      if (pos < end)
        return child.descAt(pos - offset - child.border);
      offset = end;
    }
  }
  domFromPos(pos, side) {
    if (!this.contentDOM)
      return { node: this.dom, offset: 0, atom: pos + 1 };
    let i2 = 0, offset = 0;
    for (let curPos = 0; i2 < this.children.length; i2++) {
      let child = this.children[i2], end = curPos + child.size;
      if (end > pos) {
        offset = pos - curPos;
        break;
      }
      curPos = end;
    }
    if (offset)
      return this.children[i2].domFromPos(offset - this.children[i2].border, side);
    for (; i2 > 0; i2--) {
      let prev = this.children[i2 - 1];
      if (prev.size || !(prev instanceof BufferHackViewDesc || prev instanceof WidgetViewDesc && prev.side >= 0))
        break;
    }
    if (side <= 0) {
      let prev, enter = true;
      for (; ; i2--, enter = false) {
        prev = i2 ? this.children[i2 - 1] : null;
        if (!prev || prev.dom.parentNode == this.contentDOM)
          break;
      }
      if (prev && side && enter && !prev.border && !prev.domAtom)
        return prev.domFromPos(prev.size, side);
      return { node: this.contentDOM, offset: prev ? domIndex(prev.dom) + 1 : 0 };
    } else {
      let next, enter = true;
      for (; ; i2++, enter = false) {
        next = i2 < this.children.length ? this.children[i2] : null;
        if (!next || next.dom.parentNode == this.contentDOM)
          break;
      }
      if (next && enter && !next.border && !next.domAtom)
        return next.domFromPos(0, side);
      return { node: this.contentDOM, offset: next ? domIndex(next.dom) : this.contentDOM.childNodes.length };
    }
  }
  // Used to find a DOM range in a single parent for a given changed
  // range.
  parseRange(from2, to, base2 = 0) {
    if (this.children.length == 0)
      return { node: this.contentDOM, from: from2, to, fromOffset: 0, toOffset: this.contentDOM.childNodes.length };
    let fromOffset = -1, toOffset = -1;
    for (let offset = base2, i2 = 0; ; i2++) {
      let child = this.children[i2], end = offset + child.size;
      if (fromOffset == -1 && from2 <= end) {
        let childBase = offset + child.border;
        if (from2 >= childBase && to <= end - child.border && child.node && child.contentDOM && this.contentDOM.contains(child.contentDOM))
          return child.parseRange(from2, to, childBase);
        from2 = offset;
        for (let j = i2; j > 0; j--) {
          let prev = this.children[j - 1];
          if (prev.size && prev.dom.parentNode == this.contentDOM && !prev.emptyChildAt(1)) {
            fromOffset = domIndex(prev.dom) + 1;
            break;
          }
          from2 -= prev.size;
        }
        if (fromOffset == -1)
          fromOffset = 0;
      }
      if (fromOffset > -1 && (end > to || i2 == this.children.length - 1)) {
        to = end;
        for (let j = i2 + 1; j < this.children.length; j++) {
          let next = this.children[j];
          if (next.size && next.dom.parentNode == this.contentDOM && !next.emptyChildAt(-1)) {
            toOffset = domIndex(next.dom);
            break;
          }
          to += next.size;
        }
        if (toOffset == -1)
          toOffset = this.contentDOM.childNodes.length;
        break;
      }
      offset = end;
    }
    return { node: this.contentDOM, from: from2, to, fromOffset, toOffset };
  }
  emptyChildAt(side) {
    if (this.border || !this.contentDOM || !this.children.length)
      return false;
    let child = this.children[side < 0 ? 0 : this.children.length - 1];
    return child.size == 0 || child.emptyChildAt(side);
  }
  domAfterPos(pos) {
    let { node: node2, offset } = this.domFromPos(pos, 0);
    if (!isElt(node2) || offset == node2.childNodes.length)
      throw new RangeError("No node after pos " + pos);
    return node2.childNodes[offset];
  }
  // View descs are responsible for setting any selection that falls
  // entirely inside of them, so that custom implementations can do
  // custom things with the selection. Note that this falls apart when
  // a selection starts in such a node and ends in another, in which
  // case we just use whatever domFromPos produces as a best effort.
  setSelection(anchor, head, view, force = false) {
    let from2 = Math.min(anchor, head), to = Math.max(anchor, head);
    for (let i2 = 0, offset = 0; i2 < this.children.length; i2++) {
      let child = this.children[i2], end = offset + child.size;
      if (from2 > offset && to < end)
        return child.setSelection(anchor - offset - child.border, head - offset - child.border, view, force);
      offset = end;
    }
    let anchorDOM = this.domFromPos(anchor, anchor ? -1 : 1);
    let headDOM = head == anchor ? anchorDOM : this.domFromPos(head, head ? -1 : 1);
    let domSel = view.root.getSelection();
    let selRange = view.domSelectionRange();
    let brKludge = false;
    if ((gecko || safari) && anchor == head) {
      let { node: node2, offset } = anchorDOM;
      if (isText(node2)) {
        brKludge = !!(offset && node2.nodeValue[offset - 1] == "\n");
        if (brKludge && offset == node2.nodeValue.length) {
          for (let scan = node2, after; scan; scan = scan.parentNode) {
            if (after = scan.nextSibling) {
              if (after.nodeName == "BR")
                anchorDOM = headDOM = { node: after.parentNode, offset: domIndex(after) + 1 };
              break;
            }
            let desc = scan.pmViewDesc;
            if (desc && desc.node && desc.node.isBlock)
              break;
          }
        }
      } else {
        let prev = node2.childNodes[offset - 1];
        brKludge = prev && (prev.nodeName == "BR" || prev.contentEditable == "false");
      }
    }
    if (gecko && selRange.focusNode && selRange.focusNode != headDOM.node && isElt(selRange.focusNode)) {
      let after = selRange.focusNode.childNodes[selRange.focusOffset];
      if (after && after.contentEditable == "false")
        force = true;
    }
    if (!(force || brKludge && safari) && isEquivalentPosition(anchorDOM.node, anchorDOM.offset, selRange.anchorNode, selRange.anchorOffset) && isEquivalentPosition(headDOM.node, headDOM.offset, selRange.focusNode, selRange.focusOffset))
      return;
    let domSelExtended = false;
    if ((domSel.extend || anchor == head) && !(brKludge && gecko)) {
      domSel.collapse(anchorDOM.node, anchorDOM.offset);
      try {
        if (anchor != head)
          domSel.extend(headDOM.node, headDOM.offset);
        domSelExtended = true;
      } catch (_) {
      }
    }
    if (!domSelExtended) {
      if (anchor > head) {
        let tmp = anchorDOM;
        anchorDOM = headDOM;
        headDOM = tmp;
      }
      let range = document.createRange();
      range.setEnd(headDOM.node, headDOM.offset);
      range.setStart(anchorDOM.node, anchorDOM.offset);
      domSel.removeAllRanges();
      domSel.addRange(range);
    }
  }
  ignoreMutation(mutation) {
    return !this.contentDOM && mutation.type != "selection";
  }
  get contentLost() {
    return this.contentDOM && this.contentDOM != this.dom && !this.dom.contains(this.contentDOM);
  }
  // Remove a subtree of the element tree that has been touched
  // by a DOM change, so that the next update will redraw it.
  markDirty(from2, to) {
    for (let offset = 0, i2 = 0; i2 < this.children.length; i2++) {
      let child = this.children[i2], end = offset + child.size;
      if (offset == end ? from2 <= end && to >= offset : from2 < end && to > offset) {
        let startInside = offset + child.border, endInside = end - child.border;
        if (from2 >= startInside && to <= endInside) {
          this.dirty = from2 == offset || to == end ? CONTENT_DIRTY : CHILD_DIRTY;
          if (from2 == startInside && to == endInside && (child.contentLost || child.dom.parentNode != this.contentDOM))
            child.dirty = NODE_DIRTY;
          else
            child.markDirty(from2 - startInside, to - startInside);
          return;
        } else {
          child.dirty = child.dom == child.contentDOM && child.dom.parentNode == this.contentDOM && !child.children.length ? CONTENT_DIRTY : NODE_DIRTY;
        }
      }
      offset = end;
    }
    this.dirty = CONTENT_DIRTY;
  }
  markParentsDirty() {
    let level = 1;
    for (let node2 = this.parent; node2; node2 = node2.parent, level++) {
      let dirty = level == 1 ? CONTENT_DIRTY : CHILD_DIRTY;
      if (node2.dirty < dirty)
        node2.dirty = dirty;
    }
  }
  get domAtom() {
    return false;
  }
  get ignoreForCoords() {
    return false;
  }
  get ignoreForSelection() {
    return false;
  }
  isText(text4) {
    return false;
  }
};
var WidgetViewDesc = class extends ViewDesc {
  constructor(parent, widget, view, pos) {
    let self, dom = widget.type.toDOM;
    if (typeof dom == "function")
      dom = dom(view, () => {
        if (!self)
          return pos;
        if (self.parent)
          return self.parent.posBeforeChild(self);
      });
    if (!widget.type.spec.raw) {
      let elt = isElt(dom) ? dom : document.createElement("span");
      if (elt != dom) {
        elt.appendChild(dom);
        dom = elt;
      }
      if (!elt.hasAttribute("contenteditable"))
        elt.contentEditable = "false";
      elt.classList.add("ProseMirror-widget");
    }
    super(parent, [], dom, null);
    this.widget = widget;
    this.widget = widget;
    self = this;
  }
  matchesWidget(widget) {
    return this.dirty == NOT_DIRTY && widget.type.eq(this.widget.type);
  }
  parseRule() {
    return { ignore: true };
  }
  stopEvent(event) {
    let stop = this.widget.spec.stopEvent;
    return stop ? stop(event) : false;
  }
  ignoreMutation(mutation) {
    return mutation.type != "selection" || this.widget.spec.ignoreSelection;
  }
  destroy() {
    this.widget.type.destroy(this.dom);
    super.destroy();
  }
  get domAtom() {
    return true;
  }
  get ignoreForSelection() {
    return !!this.widget.type.spec.relaxedSide;
  }
  get side() {
    return this.widget.type.side;
  }
};
var CompositionViewDesc = class extends ViewDesc {
  constructor(parent, dom, textDOM, text4) {
    super(parent, [], dom, null);
    this.textDOM = textDOM;
    this.text = text4;
  }
  get size() {
    return this.text.length;
  }
  localPosFromDOM(dom, offset) {
    if (dom != this.textDOM)
      return this.posAtStart + (offset ? this.size : 0);
    return this.posAtStart + offset;
  }
  domFromPos(pos) {
    return { node: this.textDOM, offset: pos };
  }
  ignoreMutation(mut) {
    return mut.type === "characterData" && mut.target.nodeValue == mut.oldValue;
  }
};
var MarkViewDesc = class _MarkViewDesc extends ViewDesc {
  constructor(parent, mark, dom, contentDOM, spec) {
    super(parent, [], dom, contentDOM);
    this.mark = mark;
    this.spec = spec;
  }
  static create(parent, mark, inline, view) {
    let custom = view.nodeViews[mark.type.name];
    let spec = custom && custom(mark, view, inline);
    if (!spec || !spec.dom)
      spec = DOMSerializer.renderSpec(document, mark.type.spec.toDOM(mark, inline), null, mark.attrs);
    return new _MarkViewDesc(parent, mark, spec.dom, spec.contentDOM || spec.dom, spec);
  }
  parseRule() {
    if (this.dirty & NODE_DIRTY || this.mark.type.spec.reparseInView)
      return null;
    return { mark: this.mark.type.name, attrs: this.mark.attrs, contentElement: this.contentDOM };
  }
  matchesMark(mark) {
    return this.dirty != NODE_DIRTY && this.mark.eq(mark);
  }
  markDirty(from2, to) {
    super.markDirty(from2, to);
    if (this.dirty != NOT_DIRTY) {
      let parent = this.parent;
      while (!parent.node)
        parent = parent.parent;
      if (parent.dirty < this.dirty)
        parent.dirty = this.dirty;
      this.dirty = NOT_DIRTY;
    }
  }
  slice(from2, to, view) {
    let copy2 = _MarkViewDesc.create(this.parent, this.mark, true, view);
    let nodes = this.children, size = this.size;
    if (to < size)
      nodes = replaceNodes(nodes, to, size, view);
    if (from2 > 0)
      nodes = replaceNodes(nodes, 0, from2, view);
    for (let i2 = 0; i2 < nodes.length; i2++)
      nodes[i2].parent = copy2;
    copy2.children = nodes;
    return copy2;
  }
  ignoreMutation(mutation) {
    return this.spec.ignoreMutation ? this.spec.ignoreMutation(mutation) : super.ignoreMutation(mutation);
  }
  destroy() {
    if (this.spec.destroy)
      this.spec.destroy();
    super.destroy();
  }
};
var NodeViewDesc = class _NodeViewDesc extends ViewDesc {
  constructor(parent, node2, outerDeco, innerDeco, dom, contentDOM, nodeDOM) {
    super(parent, [], dom, contentDOM);
    this.node = node2;
    this.outerDeco = outerDeco;
    this.innerDeco = innerDeco;
    this.nodeDOM = nodeDOM;
  }
  // By default, a node is rendered using the `toDOM` method from the
  // node type spec. But client code can use the `nodeViews` spec to
  // supply a custom node view, which can influence various aspects of
  // the way the node works.
  //
  // (Using subclassing for this was intentionally decided against,
  // since it'd require exposing a whole slew of finicky
  // implementation details to the user code that they probably will
  // never need.)
  static create(parent, node2, outerDeco, innerDeco, view, pos) {
    let custom = view.nodeViews[node2.type.name], descObj;
    let spec = custom && custom(node2, view, () => {
      if (!descObj)
        return pos;
      if (descObj.parent)
        return descObj.parent.posBeforeChild(descObj);
    }, outerDeco, innerDeco);
    let dom = spec && spec.dom, contentDOM = spec && spec.contentDOM;
    if (node2.isText) {
      if (!dom)
        dom = document.createTextNode(node2.text);
      else if (!isText(dom))
        throw new RangeError("Text must be rendered as a DOM text node");
    } else if (!dom) {
      let spec2 = DOMSerializer.renderSpec(document, node2.type.spec.toDOM(node2), null, node2.attrs);
      ({ dom, contentDOM } = spec2);
    }
    if (!contentDOM && !node2.isText && dom.nodeName != "BR") {
      if (!dom.hasAttribute("contenteditable"))
        dom.contentEditable = "false";
      if (node2.type.spec.draggable)
        dom.draggable = true;
    }
    let nodeDOM = dom;
    dom = applyOuterDeco(dom, outerDeco, node2);
    if (spec)
      return descObj = new CustomNodeViewDesc(parent, node2, outerDeco, innerDeco, dom, contentDOM || null, nodeDOM, spec);
    else if (node2.isText)
      return new TextViewDesc(parent, node2, outerDeco, innerDeco, dom, nodeDOM);
    else
      return new _NodeViewDesc(parent, node2, outerDeco, innerDeco, dom, contentDOM || null, nodeDOM);
  }
  parseRule(addedNodes) {
    if (this.node.type.spec.reparseInView)
      return null;
    let rule = { node: this.node.type.name, attrs: this.node.attrs };
    if (this.node.type.whitespace == "pre")
      rule.preserveWhitespace = "full";
    if (!this.contentDOM) {
      rule.getContent = () => this.node.content;
    } else if (!this.contentLost) {
      rule.contentElement = this.contentDOM;
    } else {
      for (let i2 = this.children.length - 1; i2 >= 0; i2--) {
        let child = this.children[i2];
        if (this.dom.contains(child.dom.parentNode)) {
          rule.contentElement = child.dom.parentNode;
          break;
        }
      }
      if (!rule.contentElement) {
        let found2 = addedNodes && addedNodes.find((n) => isElt(n) && addedNodes.indexOf(n.parentNode) < 0 && this.dom.contains(n));
        if (found2)
          rule.contentElement = found2;
        else
          rule.getContent = () => Fragment.empty;
      }
    }
    return rule;
  }
  matchesNode(node2, outerDeco, innerDeco) {
    return this.dirty == NOT_DIRTY && node2.eq(this.node) && sameOuterDeco(outerDeco, this.outerDeco) && innerDeco.eq(this.innerDeco);
  }
  get size() {
    return this.node.nodeSize;
  }
  get border() {
    return this.node.isLeaf ? 0 : 1;
  }
  // Syncs `this.children` to match `this.node.content` and the local
  // decorations, possibly introducing nesting for marks. Then, in a
  // separate step, syncs the DOM inside `this.contentDOM` to
  // `this.children`.
  updateChildren(view, pos) {
    let inline = this.node.inlineContent, off = pos;
    let composition = view.composing ? this.localCompositionInfo(view, pos) : null;
    let localComposition = composition && composition.pos > -1 ? composition : null;
    let compositionInChild = composition && composition.pos < 0;
    let updater = new ViewTreeUpdater(this, localComposition && localComposition.node, view);
    let addBuffers = this.node.inlineContent, atBufferPos = addBuffers && this.node.isBlock;
    iterDeco(this.node, this.innerDeco, (widget, i2, insideNode) => {
      if (widget.spec.marks)
        updater.syncToMarks(widget.spec.marks, inline, view, i2);
      else if (widget.type.side >= 0 && !insideNode)
        updater.syncToMarks(i2 == this.node.childCount ? Mark.none : this.node.child(i2).marks, inline, view, i2);
      updater.placeWidget(widget, view, off);
    }, (child, outerDeco, innerDeco, i2) => {
      updater.syncToMarks(child.marks, inline, view, i2);
      if (atBufferPos && child.isAtom && !child.isText)
        updater.addHackNode("IMG", updater.top);
      let compIndex;
      if (updater.findNodeMatch(child, outerDeco, innerDeco, i2)) ;
      else if (compositionInChild && view.state.selection.from > off && view.state.selection.to < off + child.nodeSize && (compIndex = updater.findIndexWithChild(composition.node)) > -1 && updater.updateNodeAt(child, outerDeco, innerDeco, compIndex, view)) ;
      else if (updater.updateNextNode(child, outerDeco, innerDeco, view, i2, off)) ;
      else {
        updater.addNode(child, outerDeco, innerDeco, view, off);
      }
      off += child.nodeSize;
      if (addBuffers)
        atBufferPos = child.isAtom && !child.isText;
    });
    updater.syncToMarks([], inline, view, 0);
    if (this.node.isTextblock)
      updater.addTextblockHacks();
    updater.destroyRest();
    if (updater.changed || this.dirty == CONTENT_DIRTY) {
      if (localComposition)
        this.protectLocalComposition(view, localComposition);
      renderDescs(this.contentDOM, this.children, view);
      if (ios)
        iosHacks(this.dom);
    }
  }
  localCompositionInfo(view, pos) {
    let { from: from2, to } = view.state.selection;
    if (!(view.state.selection instanceof TextSelection) || from2 < pos || to > pos + this.node.content.size)
      return null;
    let textNode = view.input.compositionNode;
    if (!textNode || !this.dom.contains(textNode.parentNode))
      return null;
    if (this.node.inlineContent) {
      let text4 = textNode.nodeValue;
      let textPos = findTextInFragment(this.node.content, text4, from2 - pos, to - pos);
      return textPos < 0 ? null : { node: textNode, pos: textPos, text: text4 };
    } else {
      return { node: textNode, pos: -1, text: "" };
    }
  }
  protectLocalComposition(view, { node: node2, pos, text: text4 }) {
    if (this.getDesc(node2))
      return;
    let topNode = node2;
    for (; ; topNode = topNode.parentNode) {
      if (topNode.parentNode == this.contentDOM)
        break;
      while (topNode.previousSibling)
        topNode.parentNode.removeChild(topNode.previousSibling);
      while (topNode.nextSibling)
        topNode.parentNode.removeChild(topNode.nextSibling);
      if (topNode.pmViewDesc)
        topNode.pmViewDesc = void 0;
    }
    let desc = new CompositionViewDesc(this, topNode, node2, text4);
    view.input.compositionNodes.push(desc);
    this.children = replaceNodes(this.children, pos, pos + text4.length, view, desc);
  }
  // If this desc must be updated to match the given node decoration,
  // do so and return true.
  update(node2, outerDeco, innerDeco, view) {
    if (this.dirty == NODE_DIRTY || !node2.sameMarkup(this.node))
      return false;
    this.updateInner(node2, outerDeco, innerDeco, view);
    return true;
  }
  updateInner(node2, outerDeco, innerDeco, view) {
    this.updateOuterDeco(outerDeco);
    this.node = node2;
    this.innerDeco = innerDeco;
    if (this.contentDOM)
      this.updateChildren(view, this.posAtStart);
    this.dirty = NOT_DIRTY;
  }
  updateOuterDeco(outerDeco) {
    if (sameOuterDeco(outerDeco, this.outerDeco))
      return;
    let needsWrap = !isElt(this.nodeDOM);
    let oldDOM = this.dom;
    this.dom = patchOuterDeco(this.dom, this.nodeDOM, computeOuterDeco(this.outerDeco, this.node, needsWrap), computeOuterDeco(outerDeco, this.node, needsWrap));
    if (this.dom != oldDOM) {
      oldDOM.pmViewDesc = void 0;
      this.dom.pmViewDesc = this;
    }
    this.outerDeco = outerDeco;
  }
  // Mark this node as being the selected node.
  selectNode() {
    if (isElt(this.nodeDOM)) {
      this.nodeDOM.classList.add("ProseMirror-selectednode");
      if (this.contentDOM || !this.node.type.spec.draggable)
        this.nodeDOM.draggable = true;
    }
  }
  // Remove selected node marking from this node.
  deselectNode() {
    if (isElt(this.nodeDOM)) {
      this.nodeDOM.classList.remove("ProseMirror-selectednode");
      if (this.contentDOM || !this.node.type.spec.draggable)
        this.nodeDOM.removeAttribute("draggable");
    }
  }
  get domAtom() {
    return this.node.isAtom;
  }
};
function docViewDesc(doc3, outerDeco, innerDeco, dom, view) {
  applyOuterDeco(dom, outerDeco, doc3);
  let docView = new NodeViewDesc(void 0, doc3, outerDeco, innerDeco, dom, dom, dom);
  if (docView.contentDOM)
    docView.updateChildren(view, 0);
  return docView;
}
var TextViewDesc = class _TextViewDesc extends NodeViewDesc {
  constructor(parent, node2, outerDeco, innerDeco, dom, nodeDOM) {
    super(parent, node2, outerDeco, innerDeco, dom, null, nodeDOM);
  }
  parseRule() {
    let skip = this.nodeDOM.parentNode;
    while (skip && skip != this.dom && !skip.pmIsDeco)
      skip = skip.parentNode;
    return { skip: skip || true };
  }
  update(node2, outerDeco, innerDeco, view) {
    if (this.dirty == NODE_DIRTY || this.dirty != NOT_DIRTY && !this.inParent() || !node2.sameMarkup(this.node))
      return false;
    this.updateOuterDeco(outerDeco);
    if ((this.dirty != NOT_DIRTY || node2.text != this.node.text) && node2.text != this.nodeDOM.nodeValue) {
      this.nodeDOM.nodeValue = node2.text;
      if (view.trackWrites == this.nodeDOM)
        view.trackWrites = null;
    }
    this.node = node2;
    this.dirty = NOT_DIRTY;
    return true;
  }
  inParent() {
    let parentDOM = this.parent.contentDOM;
    for (let n = this.nodeDOM; n; n = n.parentNode)
      if (n == parentDOM)
        return true;
    return false;
  }
  domFromPos(pos) {
    return { node: this.nodeDOM, offset: pos };
  }
  localPosFromDOM(dom, offset, bias) {
    if (dom == this.nodeDOM)
      return this.posAtStart + Math.min(offset, this.node.text.length);
    return super.localPosFromDOM(dom, offset, bias);
  }
  ignoreMutation(mutation) {
    return mutation.type != "characterData" && mutation.type != "selection";
  }
  slice(from2, to, _view) {
    let node2 = this.node.cut(from2, to), dom = document.createTextNode(node2.text);
    return new _TextViewDesc(this.parent, node2, this.outerDeco, this.innerDeco, dom, dom);
  }
  markDirty(from2, to) {
    super.markDirty(from2, to);
    if (this.dom != this.nodeDOM && (from2 == 0 || to == this.nodeDOM.nodeValue.length))
      this.dirty = NODE_DIRTY;
  }
  get domAtom() {
    return false;
  }
  isText(text4) {
    return this.node.text == text4;
  }
};
var BufferHackViewDesc = class extends ViewDesc {
  parseRule() {
    return { ignore: true };
  }
  matchesHack(nodeName) {
    return this.dirty == NOT_DIRTY && this.dom.nodeName == nodeName;
  }
  get domAtom() {
    return true;
  }
  get ignoreForCoords() {
    return this.dom.nodeName == "IMG";
  }
};
var CustomNodeViewDesc = class extends NodeViewDesc {
  constructor(parent, node2, outerDeco, innerDeco, dom, contentDOM, nodeDOM, spec) {
    super(parent, node2, outerDeco, innerDeco, dom, contentDOM, nodeDOM);
    this.spec = spec;
  }
  // A custom `update` method gets to decide whether the update goes
  // through. If it does, and there's a `contentDOM` node, our logic
  // updates the children.
  update(node2, outerDeco, innerDeco, view) {
    if (this.dirty == NODE_DIRTY)
      return false;
    if (this.spec.update && (this.node.type == node2.type || this.spec.multiType)) {
      let result = this.spec.update(node2, outerDeco, innerDeco);
      if (result)
        this.updateInner(node2, outerDeco, innerDeco, view);
      return result;
    } else if (!this.contentDOM && !node2.isLeaf) {
      return false;
    } else {
      return super.update(node2, outerDeco, innerDeco, view);
    }
  }
  selectNode() {
    this.spec.selectNode ? this.spec.selectNode() : super.selectNode();
  }
  deselectNode() {
    this.spec.deselectNode ? this.spec.deselectNode() : super.deselectNode();
  }
  setSelection(anchor, head, view, force) {
    this.spec.setSelection ? this.spec.setSelection(anchor, head, view.root) : super.setSelection(anchor, head, view, force);
  }
  destroy() {
    if (this.spec.destroy)
      this.spec.destroy();
    super.destroy();
  }
  stopEvent(event) {
    return this.spec.stopEvent ? this.spec.stopEvent(event) : false;
  }
  ignoreMutation(mutation) {
    return this.spec.ignoreMutation ? this.spec.ignoreMutation(mutation) : super.ignoreMutation(mutation);
  }
};
function renderDescs(parentDOM, descs, view) {
  let dom = parentDOM.firstChild, written = false;
  for (let i2 = 0; i2 < descs.length; i2++) {
    let desc = descs[i2], childDOM = desc.dom;
    if (childDOM.parentNode == parentDOM) {
      while (childDOM != dom) {
        dom = rm(dom);
        written = true;
      }
      dom = dom.nextSibling;
    } else {
      written = true;
      parentDOM.insertBefore(childDOM, dom);
    }
    if (desc instanceof MarkViewDesc) {
      let pos = dom ? dom.previousSibling : parentDOM.lastChild;
      renderDescs(desc.contentDOM, desc.children, view);
      dom = pos ? pos.nextSibling : parentDOM.firstChild;
    }
  }
  while (dom) {
    dom = rm(dom);
    written = true;
  }
  if (written && view.trackWrites == parentDOM)
    view.trackWrites = null;
}
var OuterDecoLevel = function(nodeName) {
  if (nodeName)
    this.nodeName = nodeName;
};
OuterDecoLevel.prototype = /* @__PURE__ */ Object.create(null);
var noDeco = [new OuterDecoLevel()];
function computeOuterDeco(outerDeco, node2, needsWrap) {
  if (outerDeco.length == 0)
    return noDeco;
  let top = needsWrap ? noDeco[0] : new OuterDecoLevel(), result = [top];
  for (let i2 = 0; i2 < outerDeco.length; i2++) {
    let attrs = outerDeco[i2].type.attrs;
    if (!attrs)
      continue;
    if (attrs.nodeName)
      result.push(top = new OuterDecoLevel(attrs.nodeName));
    for (let name in attrs) {
      let val = attrs[name];
      if (val == null)
        continue;
      if (needsWrap && result.length == 1)
        result.push(top = new OuterDecoLevel(node2.isInline ? "span" : "div"));
      if (name == "class")
        top.class = (top.class ? top.class + " " : "") + val;
      else if (name == "style")
        top.style = (top.style ? top.style + ";" : "") + val;
      else if (name != "nodeName")
        top[name] = val;
    }
  }
  return result;
}
function patchOuterDeco(outerDOM, nodeDOM, prevComputed, curComputed) {
  if (prevComputed == noDeco && curComputed == noDeco)
    return nodeDOM;
  let curDOM = nodeDOM;
  for (let i2 = 0; i2 < curComputed.length; i2++) {
    let deco = curComputed[i2], prev = prevComputed[i2];
    if (i2) {
      let parent;
      if (prev && prev.nodeName == deco.nodeName && curDOM != outerDOM && (parent = curDOM.parentNode) && parent.nodeName.toLowerCase() == deco.nodeName) {
        curDOM = parent;
      } else {
        parent = document.createElement(deco.nodeName);
        parent.pmIsDeco = true;
        parent.appendChild(curDOM);
        prev = noDeco[0];
        curDOM = parent;
      }
    }
    patchAttributes(curDOM, prev || noDeco[0], deco);
  }
  return curDOM;
}
function patchAttributes(dom, prev, cur) {
  for (let name in prev)
    if (name != "class" && name != "style" && name != "nodeName" && !(name in cur))
      dom.removeAttribute(name);
  for (let name in cur)
    if (name != "class" && name != "style" && name != "nodeName" && cur[name] != prev[name])
      dom.setAttribute(name, cur[name]);
  if (prev.class != cur.class) {
    let prevList = prev.class ? prev.class.split(" ").filter(Boolean) : [];
    let curList = cur.class ? cur.class.split(" ").filter(Boolean) : [];
    for (let i2 = 0; i2 < prevList.length; i2++)
      if (curList.indexOf(prevList[i2]) == -1)
        dom.classList.remove(prevList[i2]);
    for (let i2 = 0; i2 < curList.length; i2++)
      if (prevList.indexOf(curList[i2]) == -1)
        dom.classList.add(curList[i2]);
    if (dom.classList.length == 0)
      dom.removeAttribute("class");
  }
  if (prev.style != cur.style) {
    if (prev.style) {
      let prop = /\s*([\w\-\xa1-\uffff]+)\s*:(?:"(?:\\.|[^"])*"|'(?:\\.|[^'])*'|\(.*?\)|[^;])*/g, m;
      while (m = prop.exec(prev.style))
        dom.style.removeProperty(m[1]);
    }
    if (cur.style)
      dom.style.cssText += cur.style;
  }
}
function applyOuterDeco(dom, deco, node2) {
  return patchOuterDeco(dom, dom, noDeco, computeOuterDeco(deco, node2, !isElt(dom)));
}
function sameOuterDeco(a, b) {
  if (a.length != b.length)
    return false;
  for (let i2 = 0; i2 < a.length; i2++)
    if (!a[i2].type.eq(b[i2].type))
      return false;
  return true;
}
function rm(dom) {
  let next = dom.nextSibling;
  dom.parentNode.removeChild(dom);
  return next;
}
var ViewTreeUpdater = class {
  constructor(top, lock, view) {
    this.lock = lock;
    this.view = view;
    this.index = 0;
    this.stack = [];
    this.changed = false;
    this.top = top;
    this.preMatch = preMatch(top.node.content, top);
  }
  // Destroy and remove the children between the given indices in
  // `this.top`.
  destroyBetween(start, end) {
    if (start == end)
      return;
    for (let i2 = start; i2 < end; i2++)
      this.top.children[i2].destroy();
    this.top.children.splice(start, end - start);
    this.changed = true;
  }
  // Destroy all remaining children in `this.top`.
  destroyRest() {
    this.destroyBetween(this.index, this.top.children.length);
  }
  // Sync the current stack of mark descs with the given array of
  // marks, reusing existing mark descs when possible.
  syncToMarks(marks, inline, view, parentIndex) {
    let keep = 0, depth = this.stack.length >> 1;
    let maxKeep = Math.min(depth, marks.length);
    while (keep < maxKeep && (keep == depth - 1 ? this.top : this.stack[keep + 1 << 1]).matchesMark(marks[keep]) && marks[keep].type.spec.spanning !== false)
      keep++;
    while (keep < depth) {
      this.destroyRest();
      this.top.dirty = NOT_DIRTY;
      this.index = this.stack.pop();
      this.top = this.stack.pop();
      depth--;
    }
    while (depth < marks.length) {
      this.stack.push(this.top, this.index + 1);
      let found2 = -1, scanTo = this.top.children.length;
      if (parentIndex < this.preMatch.index)
        scanTo = Math.min(this.index + 3, scanTo);
      for (let i2 = this.index; i2 < scanTo; i2++) {
        let next = this.top.children[i2];
        if (next.matchesMark(marks[depth]) && !this.isLocked(next.dom)) {
          found2 = i2;
          break;
        }
      }
      if (found2 < 0 && this.index < this.top.children.length) {
        let cur = this.top.children[this.index];
        if (cur instanceof MarkViewDesc && cur.dirty != NODE_DIRTY && cur.mark.type == marks[depth].type && cur.spec.update && !this.isLocked(cur.dom) && cur.spec.update(marks[depth])) {
          cur.mark = marks[depth];
          found2 = this.index;
          this.changed = true;
        }
      }
      if (found2 > -1) {
        if (found2 > this.index) {
          this.changed = true;
          this.destroyBetween(this.index, found2);
        }
        this.top = this.top.children[this.index];
      } else {
        let markDesc = MarkViewDesc.create(this.top, marks[depth], inline, view);
        this.top.children.splice(this.index, 0, markDesc);
        this.top = markDesc;
        this.changed = true;
      }
      this.index = 0;
      depth++;
    }
  }
  // Try to find a node desc matching the given data. Skip over it and
  // return true when successful.
  findNodeMatch(node2, outerDeco, innerDeco, index2) {
    let found2 = -1, targetDesc;
    if (index2 >= this.preMatch.index && (targetDesc = this.preMatch.matches[index2 - this.preMatch.index]).parent == this.top && targetDesc.matchesNode(node2, outerDeco, innerDeco)) {
      found2 = this.top.children.indexOf(targetDesc, this.index);
    } else {
      for (let i2 = this.index, e = Math.min(this.top.children.length, i2 + 5); i2 < e; i2++) {
        let child = this.top.children[i2];
        if (child.matchesNode(node2, outerDeco, innerDeco) && !this.preMatch.matched.has(child)) {
          found2 = i2;
          break;
        }
      }
    }
    if (found2 < 0)
      return false;
    this.destroyBetween(this.index, found2);
    this.index++;
    return true;
  }
  updateNodeAt(node2, outerDeco, innerDeco, index2, view) {
    let child = this.top.children[index2];
    if (child.dirty == NODE_DIRTY && child.dom == child.contentDOM)
      child.dirty = CONTENT_DIRTY;
    if (!child.update(node2, outerDeco, innerDeco, view))
      return false;
    this.destroyBetween(this.index, index2);
    this.index++;
    return true;
  }
  findIndexWithChild(domNode) {
    for (; ; ) {
      let parent = domNode.parentNode;
      if (!parent)
        return -1;
      if (parent == this.top.contentDOM) {
        let desc = domNode.pmViewDesc;
        if (desc)
          for (let i2 = this.index; i2 < this.top.children.length; i2++) {
            if (this.top.children[i2] == desc)
              return i2;
          }
        return -1;
      }
      domNode = parent;
    }
  }
  // Try to update the next node, if any, to the given data. Checks
  // pre-matches to avoid overwriting nodes that could still be used.
  updateNextNode(node2, outerDeco, innerDeco, view, index2, pos) {
    for (let i2 = this.index; i2 < this.top.children.length; i2++) {
      let next = this.top.children[i2];
      if (next instanceof NodeViewDesc) {
        let preMatch2 = this.preMatch.matched.get(next);
        if (preMatch2 != null && preMatch2 != index2)
          return false;
        let nextDOM = next.dom, updated;
        let locked = this.isLocked(nextDOM) && !(node2.isText && next.node && next.node.isText && next.nodeDOM.nodeValue == node2.text && next.dirty != NODE_DIRTY && sameOuterDeco(outerDeco, next.outerDeco));
        if (!locked && next.update(node2, outerDeco, innerDeco, view)) {
          this.destroyBetween(this.index, i2);
          if (next.dom != nextDOM)
            this.changed = true;
          this.index++;
          return true;
        } else if (!locked && (updated = this.recreateWrapper(next, node2, outerDeco, innerDeco, view, pos))) {
          this.destroyBetween(this.index, i2);
          this.top.children[this.index] = updated;
          if (updated.contentDOM) {
            updated.dirty = CONTENT_DIRTY;
            updated.updateChildren(view, pos + 1);
            updated.dirty = NOT_DIRTY;
          }
          this.changed = true;
          this.index++;
          return true;
        }
        break;
      }
    }
    return false;
  }
  // When a node with content is replaced by a different node with
  // identical content, move over its children.
  recreateWrapper(next, node2, outerDeco, innerDeco, view, pos) {
    if (next.dirty || node2.isAtom || !next.children.length || !next.node.content.eq(node2.content) || !sameOuterDeco(outerDeco, next.outerDeco) || !innerDeco.eq(next.innerDeco))
      return null;
    let wrapper = NodeViewDesc.create(this.top, node2, outerDeco, innerDeco, view, pos);
    if (wrapper.contentDOM) {
      wrapper.children = next.children;
      next.children = [];
      for (let ch of wrapper.children)
        ch.parent = wrapper;
    }
    next.destroy();
    return wrapper;
  }
  // Insert the node as a newly created node desc.
  addNode(node2, outerDeco, innerDeco, view, pos) {
    let desc = NodeViewDesc.create(this.top, node2, outerDeco, innerDeco, view, pos);
    if (desc.contentDOM)
      desc.updateChildren(view, pos + 1);
    this.top.children.splice(this.index++, 0, desc);
    this.changed = true;
  }
  placeWidget(widget, view, pos) {
    let next = this.index < this.top.children.length ? this.top.children[this.index] : null;
    if (next && next.matchesWidget(widget) && (widget == next.widget || !next.widget.type.toDOM.parentNode)) {
      this.index++;
    } else {
      let desc = new WidgetViewDesc(this.top, widget, view, pos);
      this.top.children.splice(this.index++, 0, desc);
      this.changed = true;
    }
  }
  // Make sure a textblock looks and behaves correctly in
  // contentEditable.
  addTextblockHacks() {
    let lastChild = this.top.children[this.index - 1], parent = this.top;
    while (lastChild instanceof MarkViewDesc) {
      parent = lastChild;
      lastChild = parent.children[parent.children.length - 1];
    }
    if (!lastChild || // Empty textblock
    !(lastChild instanceof TextViewDesc) || /\n$/.test(lastChild.node.text) || this.view.requiresGeckoHackNode && /\s$/.test(lastChild.node.text)) {
      if ((safari || chrome) && lastChild && lastChild.dom.contentEditable == "false")
        this.addHackNode("IMG", parent);
      this.addHackNode("BR", this.top);
    }
  }
  addHackNode(nodeName, parent) {
    if (parent == this.top && this.index < parent.children.length && parent.children[this.index].matchesHack(nodeName)) {
      this.index++;
    } else {
      let dom = document.createElement(nodeName);
      if (nodeName == "IMG") {
        dom.className = "ProseMirror-separator";
        dom.alt = "";
      }
      if (nodeName == "BR")
        dom.className = "ProseMirror-trailingBreak";
      let hack = new BufferHackViewDesc(this.top, [], dom, null);
      if (parent != this.top)
        parent.children.push(hack);
      else
        parent.children.splice(this.index++, 0, hack);
      this.changed = true;
    }
  }
  isLocked(node2) {
    return this.lock && (node2 == this.lock || isElt(node2) && node2.contains(this.lock.parentNode));
  }
};
function preMatch(frag, parentDesc) {
  let curDesc = parentDesc, descI = curDesc.children.length;
  let fI = frag.childCount, matched = /* @__PURE__ */ new Map(), matches2 = [];
  outer: while (fI > 0) {
    let desc;
    for (; ; ) {
      if (descI) {
        let next = curDesc.children[descI - 1];
        if (next instanceof MarkViewDesc) {
          curDesc = next;
          descI = next.children.length;
        } else {
          desc = next;
          descI--;
          break;
        }
      } else if (curDesc == parentDesc) {
        break outer;
      } else {
        descI = curDesc.parent.children.indexOf(curDesc);
        curDesc = curDesc.parent;
      }
    }
    let node2 = desc.node;
    if (!node2)
      continue;
    if (node2 != frag.child(fI - 1))
      break;
    --fI;
    matched.set(desc, fI);
    matches2.push(desc);
  }
  return { index: fI, matched, matches: matches2.reverse() };
}
function compareSide(a, b) {
  return a.type.side - b.type.side;
}
function iterDeco(parent, deco, onWidget, onNode) {
  let locals = deco.locals(parent), offset = 0;
  if (locals.length == 0) {
    for (let i2 = 0; i2 < parent.childCount; i2++) {
      let child = parent.child(i2);
      onNode(child, locals, deco.forChild(offset, child), i2);
      offset += child.nodeSize;
    }
    return;
  }
  let decoIndex = 0, active = [], restNode = null;
  for (let parentIndex = 0; ; ) {
    let widget, widgets;
    while (decoIndex < locals.length && locals[decoIndex].to == offset) {
      let next = locals[decoIndex++];
      if (next.widget) {
        if (!widget)
          widget = next;
        else
          (widgets || (widgets = [widget])).push(next);
      }
    }
    if (widget) {
      if (widgets) {
        widgets.sort(compareSide);
        for (let i2 = 0; i2 < widgets.length; i2++)
          onWidget(widgets[i2], parentIndex, !!restNode);
      } else {
        onWidget(widget, parentIndex, !!restNode);
      }
    }
    let child, index2;
    if (restNode) {
      index2 = -1;
      child = restNode;
      restNode = null;
    } else if (parentIndex < parent.childCount) {
      index2 = parentIndex;
      child = parent.child(parentIndex++);
    } else {
      break;
    }
    for (let i2 = 0; i2 < active.length; i2++)
      if (active[i2].to <= offset)
        active.splice(i2--, 1);
    while (decoIndex < locals.length && locals[decoIndex].from <= offset && locals[decoIndex].to > offset)
      active.push(locals[decoIndex++]);
    let end = offset + child.nodeSize;
    if (child.isText) {
      let cutAt = end;
      if (decoIndex < locals.length && locals[decoIndex].from < cutAt)
        cutAt = locals[decoIndex].from;
      for (let i2 = 0; i2 < active.length; i2++)
        if (active[i2].to < cutAt)
          cutAt = active[i2].to;
      if (cutAt < end) {
        restNode = child.cut(cutAt - offset);
        child = child.cut(0, cutAt - offset);
        end = cutAt;
        index2 = -1;
      }
    } else {
      while (decoIndex < locals.length && locals[decoIndex].to < end)
        decoIndex++;
    }
    let outerDeco = child.isInline && !child.isLeaf ? active.filter((d) => !d.inline) : active.slice();
    onNode(child, outerDeco, deco.forChild(offset, child), index2);
    offset = end;
  }
}
function iosHacks(dom) {
  if (dom.nodeName == "UL" || dom.nodeName == "OL") {
    let oldCSS = dom.style.cssText;
    dom.style.cssText = oldCSS + "; list-style: square !important";
    window.getComputedStyle(dom).listStyle;
    dom.style.cssText = oldCSS;
  }
}
function findTextInFragment(frag, text4, from2, to) {
  for (let i2 = 0, pos = 0; i2 < frag.childCount && pos <= to; ) {
    let child = frag.child(i2++), childStart = pos;
    pos += child.nodeSize;
    if (!child.isText)
      continue;
    let str = child.text;
    while (i2 < frag.childCount) {
      let next = frag.child(i2++);
      pos += next.nodeSize;
      if (!next.isText)
        break;
      str += next.text;
    }
    if (pos >= from2) {
      if (pos >= to && str.slice(to - text4.length - childStart, to - childStart) == text4)
        return to - text4.length;
      let found2 = childStart < to ? str.lastIndexOf(text4, to - childStart - 1) : -1;
      if (found2 >= 0 && found2 + text4.length + childStart >= from2)
        return childStart + found2;
      if (from2 == to && str.length >= to + text4.length - childStart && str.slice(to - childStart, to - childStart + text4.length) == text4)
        return to;
    }
  }
  return -1;
}
function replaceNodes(nodes, from2, to, view, replacement) {
  let result = [];
  for (let i2 = 0, off = 0; i2 < nodes.length; i2++) {
    let child = nodes[i2], start = off, end = off += child.size;
    if (start >= to || end <= from2) {
      result.push(child);
    } else {
      if (start < from2)
        result.push(child.slice(0, from2 - start, view));
      if (replacement) {
        result.push(replacement);
        replacement = void 0;
      }
      if (end > to)
        result.push(child.slice(to - start, child.size, view));
    }
  }
  return result;
}
function selectionFromDOM(view, origin = null) {
  let domSel = view.domSelectionRange(), doc3 = view.state.doc;
  if (!domSel.focusNode)
    return null;
  let nearestDesc = view.docView.nearestDesc(domSel.focusNode), inWidget = nearestDesc && nearestDesc.size == 0;
  let head = view.docView.posFromDOM(domSel.focusNode, domSel.focusOffset, 1);
  if (head < 0)
    return null;
  let $head = doc3.resolve(head), anchor, selection;
  if (selectionCollapsed(domSel)) {
    anchor = head;
    while (nearestDesc && !nearestDesc.node)
      nearestDesc = nearestDesc.parent;
    if (nearestDesc && nearestDesc.node.isAtom && NodeSelection.isSelectable(nearestDesc.node) && nearestDesc.parent && !(nearestDesc.node.isInline && isOnEdge(domSel.focusNode, domSel.focusOffset, nearestDesc.dom))) {
      let pos = nearestDesc.posBefore;
      selection = new NodeSelection(head == pos ? $head : doc3.resolve(pos));
    } else if (gecko && origin == "key" && head > view.state.selection.to && isElt(domSel.focusNode) && domSel.focusOffset == domSel.focusNode.childNodes.length && nearestDesc && nearestDesc.posAtStart > view.state.selection.to) {
      for (let scan = domSel.focusNode; ; scan = scan.parentNode) {
        if (getComputedStyle(scan).overflow != "visible") {
          selection = Selection.findFrom(doc3.resolve(nearestDesc.posAtStart), 1);
          break;
        }
        if (scan == nearestDesc.dom || scan.nextSibling || !scan.parentNode || !isElt(scan.parentNode))
          break;
      }
    }
  } else {
    if (domSel instanceof view.dom.ownerDocument.defaultView.Selection && domSel.rangeCount > 1) {
      let min = head, max = head;
      for (let i2 = 0; i2 < domSel.rangeCount; i2++) {
        let range = domSel.getRangeAt(i2);
        min = Math.min(min, view.docView.posFromDOM(range.startContainer, range.startOffset, 1));
        max = Math.max(max, view.docView.posFromDOM(range.endContainer, range.endOffset, -1));
      }
      if (min < 0)
        return null;
      [anchor, head] = max == view.state.selection.anchor ? [max, min] : [min, max];
      $head = doc3.resolve(head);
    } else {
      anchor = view.docView.posFromDOM(domSel.anchorNode, domSel.anchorOffset, 1);
    }
    if (anchor < 0)
      return null;
  }
  let $anchor = doc3.resolve(anchor);
  if (!selection) {
    let bias = origin == "pointer" || view.state.selection.head < $head.pos && !inWidget ? 1 : -1;
    selection = selectionBetween(view, $anchor, $head, bias);
  }
  return selection;
}
function editorOwnsSelection(view) {
  return view.editable ? view.hasFocus() : hasSelection(view) && document.activeElement && document.activeElement.contains(view.dom);
}
function selectionToDOM(view, force = false) {
  let sel = view.state.selection;
  syncNodeSelection(view, sel);
  if (!editorOwnsSelection(view))
    return;
  let mouseDown = view.input.mouseDown;
  if (!force && chrome && mouseDown) {
    let domSel = view.domSelectionRange(), curSel = view.domObserver.currentSelection;
    if (domSel.anchorNode && curSel.anchorNode && isEquivalentPosition(domSel.anchorNode, domSel.anchorOffset, curSel.anchorNode, curSel.anchorOffset) && mouseDown.delaySelUpdate()) {
      view.domObserver.setCurSelection();
      return;
    }
  }
  view.domObserver.disconnectSelection();
  if (view.cursorWrapper) {
    selectCursorWrapper(view);
  } else {
    let { anchor, head } = sel, resetEditableFrom, resetEditableTo;
    if (brokenSelectBetweenUneditable && !(sel instanceof TextSelection)) {
      if (!sel.$from.parent.inlineContent)
        resetEditableFrom = temporarilyEditableNear(view, sel.from);
      if (!sel.empty && !sel.$from.parent.inlineContent)
        resetEditableTo = temporarilyEditableNear(view, sel.to);
    }
    view.docView.setSelection(anchor, head, view, force);
    if (brokenSelectBetweenUneditable) {
      if (resetEditableFrom)
        resetEditable(resetEditableFrom);
      if (resetEditableTo)
        resetEditable(resetEditableTo);
    }
    if (sel.visible) {
      view.dom.classList.remove("ProseMirror-hideselection");
    } else {
      view.dom.classList.add("ProseMirror-hideselection");
      if ("onselectionchange" in document)
        removeClassOnSelectionChange(view);
    }
  }
  view.domObserver.setCurSelection();
  view.domObserver.connectSelection();
}
var brokenSelectBetweenUneditable = safari || chrome && chrome_version < 63;
function temporarilyEditableNear(view, pos) {
  let { node: node2, offset } = view.docView.domFromPos(pos, 0);
  let after = offset < node2.childNodes.length ? node2.childNodes[offset] : null;
  let before = offset ? node2.childNodes[offset - 1] : null;
  if (safari && after && after.contentEditable == "false")
    return setEditable(after);
  if ((!after || after.contentEditable == "false") && (!before || before.contentEditable == "false")) {
    if (after)
      return setEditable(after);
    else if (before)
      return setEditable(before);
  }
}
function setEditable(element) {
  element.contentEditable = "true";
  if (safari && element.draggable) {
    element.draggable = false;
    element.wasDraggable = true;
  }
  return element;
}
function resetEditable(element) {
  element.contentEditable = "false";
  if (element.wasDraggable) {
    element.draggable = true;
    element.wasDraggable = null;
  }
}
function removeClassOnSelectionChange(view) {
  let doc3 = view.dom.ownerDocument;
  doc3.removeEventListener("selectionchange", view.input.hideSelectionGuard);
  let domSel = view.domSelectionRange();
  let node2 = domSel.anchorNode, offset = domSel.anchorOffset;
  doc3.addEventListener("selectionchange", view.input.hideSelectionGuard = () => {
    if (domSel.anchorNode != node2 || domSel.anchorOffset != offset) {
      doc3.removeEventListener("selectionchange", view.input.hideSelectionGuard);
      setTimeout(() => {
        if (!editorOwnsSelection(view) || view.state.selection.visible)
          view.dom.classList.remove("ProseMirror-hideselection");
      }, 20);
    }
  });
}
function selectCursorWrapper(view) {
  let domSel = view.domSelection();
  if (!domSel)
    return;
  let node2 = view.cursorWrapper.dom, img = node2.nodeName == "IMG";
  if (img)
    domSel.collapse(node2.parentNode, domIndex(node2) + 1);
  else
    domSel.collapse(node2, 0);
  if (!img && !view.state.selection.visible && ie && ie_version <= 11) {
    node2.disabled = true;
    node2.disabled = false;
  }
}
function syncNodeSelection(view, sel) {
  if (sel instanceof NodeSelection) {
    let desc = view.docView.descAt(sel.from);
    if (desc != view.lastSelectedViewDesc) {
      clearNodeSelection(view);
      if (desc)
        desc.selectNode();
      view.lastSelectedViewDesc = desc;
    }
  } else {
    clearNodeSelection(view);
  }
}
function clearNodeSelection(view) {
  if (view.lastSelectedViewDesc) {
    if (view.lastSelectedViewDesc.parent)
      view.lastSelectedViewDesc.deselectNode();
    view.lastSelectedViewDesc = void 0;
  }
}
function selectionBetween(view, $anchor, $head, bias) {
  return view.someProp("createSelectionBetween", (f) => f(view, $anchor, $head)) || TextSelection.between($anchor, $head, bias);
}
function hasFocusAndSelection(view) {
  if (view.editable && !view.hasFocus())
    return false;
  return hasSelection(view);
}
function hasSelection(view) {
  let sel = view.domSelectionRange();
  if (!sel.anchorNode)
    return false;
  try {
    return contains(view.dom, sel.anchorNode) && (view.editable || contains(view.dom, sel.focusNode));
  } catch (_) {
    return false;
  }
}
function anchorInRightPlace(view) {
  let anchorDOM = view.docView.domFromPos(view.state.selection.anchor, 0);
  let domSel = view.domSelectionRange();
  return isEquivalentPosition(anchorDOM.node, anchorDOM.offset, domSel.anchorNode, domSel.anchorOffset);
}
function moveSelectionBlock(state, dir) {
  let { $anchor, $head } = state.selection;
  let $side = dir > 0 ? $anchor.max($head) : $anchor.min($head);
  let $start = !$side.parent.inlineContent ? $side : $side.depth ? state.doc.resolve(dir > 0 ? $side.after() : $side.before()) : null;
  return $start && Selection.findFrom($start, dir);
}
function apply(view, sel) {
  view.dispatch(view.state.tr.setSelection(sel).scrollIntoView());
  return true;
}
function selectHorizontally(view, dir, mods) {
  let sel = view.state.selection;
  if (sel instanceof TextSelection) {
    if (mods.indexOf("s") > -1) {
      let { $head } = sel, node2 = $head.textOffset ? null : dir < 0 ? $head.nodeBefore : $head.nodeAfter;
      if (!node2 || node2.isText || !node2.isLeaf)
        return false;
      let $newHead = view.state.doc.resolve($head.pos + node2.nodeSize * (dir < 0 ? -1 : 1));
      return apply(view, new TextSelection(sel.$anchor, $newHead));
    } else if (!sel.empty) {
      return false;
    } else if (view.endOfTextblock(dir > 0 ? "forward" : "backward")) {
      let next = moveSelectionBlock(view.state, dir);
      if (next && next instanceof NodeSelection)
        return apply(view, next);
      return false;
    } else if (!mac || mods.indexOf("m") < 0) {
      let $head = sel.$head, node2 = $head.textOffset ? null : dir < 0 ? $head.nodeBefore : $head.nodeAfter, desc;
      if (!node2 || node2.isText)
        return false;
      let nodePos = dir < 0 ? $head.pos - node2.nodeSize : $head.pos;
      if (!(node2.isAtom || (desc = view.docView.descAt(nodePos)) && !desc.contentDOM))
        return false;
      if (NodeSelection.isSelectable(node2)) {
        return apply(view, new NodeSelection(dir < 0 ? view.state.doc.resolve($head.pos - node2.nodeSize) : $head));
      } else {
        return apply(view, new TextSelection(view.state.doc.resolve(dir < 0 ? nodePos : nodePos + node2.nodeSize)));
      }
    }
  } else if (sel instanceof NodeSelection && sel.node.isInline) {
    return apply(view, new TextSelection(dir > 0 ? sel.$to : sel.$from));
  } else {
    let next = moveSelectionBlock(view.state, dir);
    if (next)
      return apply(view, next);
    return false;
  }
}
function isIgnorable(dom, dir) {
  let desc = dom.pmViewDesc;
  return desc ? desc.size == 0 && (dir < 0 || dom.nextSibling || dom.nodeName != "BR") : isElt(dom) && dom.contentEditable == "false";
}
function skipIgnoredNodes(view, dir) {
  return dir < 0 ? skipIgnoredNodesBefore(view) : skipIgnoredNodesAfter(view);
}
function skipIgnoredNodesBefore(view) {
  let sel = view.domSelectionRange();
  let node2 = sel.focusNode, offset = sel.focusOffset;
  if (!node2)
    return;
  let moveNode, moveOffset, force = false;
  if (gecko && isElt(node2) && offset < nodeSize(node2) && isIgnorable(node2.childNodes[offset], -1))
    force = true;
  for (; ; ) {
    if (offset > 0) {
      if (!isElt(node2))
        break;
      let before = node2.childNodes[offset - 1];
      if (isIgnorable(before, -1)) {
        moveNode = node2;
        moveOffset = --offset;
      } else if (isText(before)) {
        node2 = before;
        offset = node2.nodeValue.length;
      } else {
        break;
      }
    } else if (isBlockNode(node2)) {
      break;
    } else {
      let prev = node2.previousSibling;
      while (prev && isIgnorable(prev, -1)) {
        moveNode = node2.parentNode;
        moveOffset = domIndex(prev);
        prev = prev.previousSibling;
      }
      if (!prev) {
        node2 = node2.parentNode;
        if (node2 == view.dom)
          break;
        offset = 0;
      } else {
        node2 = prev;
        offset = nodeSize(node2);
      }
    }
  }
  if (force)
    setSelFocus(view, node2, offset);
  else if (moveNode)
    setSelFocus(view, moveNode, moveOffset);
}
function skipIgnoredNodesAfter(view) {
  let sel = view.domSelectionRange();
  let node2 = sel.focusNode, offset = sel.focusOffset;
  if (!node2)
    return;
  let len = nodeSize(node2);
  let moveNode, moveOffset;
  for (; ; ) {
    if (offset < len) {
      if (!isElt(node2))
        break;
      let after = node2.childNodes[offset];
      if (isIgnorable(after, 1)) {
        moveNode = node2;
        moveOffset = ++offset;
      } else {
        break;
      }
    } else if (isBlockNode(node2)) {
      break;
    } else {
      let next = node2.nextSibling;
      while (next && isIgnorable(next, 1)) {
        moveNode = next.parentNode;
        moveOffset = domIndex(next) + 1;
        next = next.nextSibling;
      }
      if (!next) {
        node2 = node2.parentNode;
        if (node2 == view.dom)
          break;
        offset = len = 0;
      } else {
        node2 = next;
        offset = 0;
        len = nodeSize(node2);
      }
    }
  }
  if (moveNode)
    setSelFocus(view, moveNode, moveOffset);
}
function isBlockNode(dom) {
  let desc = dom.pmViewDesc;
  return desc && desc.node && desc.node.isBlock;
}
function textNodeAfter(node2, offset) {
  while (node2 && offset == node2.childNodes.length && !hasBlockDesc(node2)) {
    offset = domIndex(node2) + 1;
    node2 = node2.parentNode;
  }
  while (node2 && offset < node2.childNodes.length) {
    let next = node2.childNodes[offset];
    if (isText(next))
      return next;
    if (isElt(next) && next.contentEditable == "false")
      break;
    node2 = next;
    offset = 0;
  }
}
function textNodeBefore(node2, offset) {
  while (node2 && !offset && !hasBlockDesc(node2)) {
    offset = domIndex(node2);
    node2 = node2.parentNode;
  }
  while (node2 && offset) {
    let next = node2.childNodes[offset - 1];
    if (isText(next))
      return next;
    if (isElt(next) && next.contentEditable == "false")
      break;
    node2 = next;
    offset = node2.childNodes.length;
  }
}
function setSelFocus(view, node2, offset) {
  if (!isText(node2)) {
    let before, after;
    if (after = textNodeAfter(node2, offset)) {
      node2 = after;
      offset = 0;
    } else if (before = textNodeBefore(node2, offset)) {
      node2 = before;
      offset = before.nodeValue.length;
    }
  }
  let sel = view.domSelection(), range = view.domSelectionRange();
  if (!sel)
    return;
  if (selectionCollapsed(range)) {
    sel.collapse(node2, offset);
  } else if (sel.extend) {
    sel.collapse(range.anchorNode, range.anchorOffset);
    sel.extend(node2, offset);
  }
  view.domObserver.setCurSelection();
  let { state } = view;
  setTimeout(() => {
    if (view.state == state)
      selectionToDOM(view);
  }, 50);
}
function findDirection(view, pos) {
  let $pos = view.state.doc.resolve(pos);
  if (!(chrome || windows) && $pos.parent.inlineContent) {
    let coords = view.coordsAtPos(pos);
    if (pos > $pos.start()) {
      let before = view.coordsAtPos(pos - 1);
      let mid = (before.top + before.bottom) / 2;
      if (mid > coords.top && mid < coords.bottom && Math.abs(before.left - coords.left) > 1)
        return before.left < coords.left ? "ltr" : "rtl";
    }
    if (pos < $pos.end()) {
      let after = view.coordsAtPos(pos + 1);
      let mid = (after.top + after.bottom) / 2;
      if (mid > coords.top && mid < coords.bottom && Math.abs(after.left - coords.left) > 1)
        return after.left > coords.left ? "ltr" : "rtl";
    }
  }
  let block = view.dom;
  for (let d = $pos.depth; d > 0; d--)
    if ($pos.node(d).isBlock) {
      block = view.nodeDOM($pos.before(d)) || block;
      break;
    }
  let computed = getComputedStyle(block).direction;
  return computed == "rtl" ? "rtl" : "ltr";
}
function selectVertically(view, dir, mods) {
  let sel = view.state.selection;
  if (sel instanceof TextSelection && !sel.empty || mods.indexOf("s") > -1)
    return false;
  if (mac && mods.indexOf("m") > -1)
    return false;
  let { $from, $to } = sel;
  if (!$from.parent.inlineContent || view.endOfTextblock(dir < 0 ? "up" : "down")) {
    let next = moveSelectionBlock(view.state, dir);
    if (next && next instanceof NodeSelection)
      return apply(view, next);
  }
  if (!$from.parent.inlineContent) {
    let side = dir < 0 ? $from : $to;
    let beyond = sel instanceof AllSelection ? Selection.near(side, dir) : Selection.findFrom(side, dir);
    return beyond ? apply(view, beyond) : false;
  }
  return false;
}
function stopNativeHorizontalDelete(view, dir) {
  if (!(view.state.selection instanceof TextSelection))
    return true;
  let { $head, $anchor, empty: empty3 } = view.state.selection;
  if (!$head.sameParent($anchor))
    return true;
  if (!empty3)
    return false;
  if (view.endOfTextblock(dir > 0 ? "forward" : "backward"))
    return true;
  let nextNode = !$head.textOffset && (dir < 0 ? $head.nodeBefore : $head.nodeAfter);
  if (nextNode && !nextNode.isText) {
    let tr = view.state.tr;
    if (dir < 0)
      tr.delete($head.pos - nextNode.nodeSize, $head.pos);
    else
      tr.delete($head.pos, $head.pos + nextNode.nodeSize);
    view.dispatch(tr);
    return true;
  }
  return false;
}
function switchEditable(view, node2, state) {
  view.domObserver.stop();
  node2.contentEditable = state;
  view.domObserver.start();
}
function safariDownArrowBug(view) {
  if (!safari || view.state.selection.$head.parentOffset > 0)
    return false;
  let { focusNode, focusOffset } = view.domSelectionRange();
  if (focusNode && isElt(focusNode) && focusOffset == 0 && focusNode.firstChild && isElt(focusNode.firstChild) && focusNode.firstChild.contentEditable == "false") {
    let child = focusNode.firstChild;
    switchEditable(view, child, "true");
    setTimeout(() => switchEditable(view, child, "false"), 20);
  }
  return false;
}
function getMods(event) {
  let result = "";
  if (event.ctrlKey)
    result += "c";
  if (event.metaKey)
    result += "m";
  if (event.altKey)
    result += "a";
  if (event.shiftKey)
    result += "s";
  return result;
}
function captureKeyDown(view, event) {
  let code4 = event.keyCode, mods = getMods(event);
  if (code4 == 8 || mac && code4 == 72 && mods == "c") {
    return stopNativeHorizontalDelete(view, -1) || skipIgnoredNodes(view, -1);
  } else if (code4 == 46 && !event.shiftKey || mac && code4 == 68 && mods == "c") {
    return stopNativeHorizontalDelete(view, 1) || skipIgnoredNodes(view, 1);
  } else if (code4 == 13 || code4 == 27) {
    return true;
  } else if (code4 == 37 || mac && code4 == 66 && mods == "c") {
    let dir = code4 == 37 ? findDirection(view, view.state.selection.from) == "ltr" ? -1 : 1 : -1;
    return selectHorizontally(view, dir, mods) || skipIgnoredNodes(view, dir);
  } else if (code4 == 39 || mac && code4 == 70 && mods == "c") {
    let dir = code4 == 39 ? findDirection(view, view.state.selection.from) == "ltr" ? 1 : -1 : 1;
    return selectHorizontally(view, dir, mods) || skipIgnoredNodes(view, dir);
  } else if (code4 == 38 || mac && code4 == 80 && mods == "c") {
    return selectVertically(view, -1, mods) || skipIgnoredNodes(view, -1);
  } else if (code4 == 40 || mac && code4 == 78 && mods == "c") {
    return safariDownArrowBug(view) || selectVertically(view, 1, mods) || skipIgnoredNodes(view, 1);
  } else if (mods == (mac ? "m" : "c") && (code4 == 66 || code4 == 73 || code4 == 89 || code4 == 90)) {
    return true;
  }
  return false;
}
function serializeForClipboard(view, slice2) {
  view.someProp("transformCopied", (f) => {
    slice2 = f(slice2, view);
  });
  let context = [], { content: content3, openStart, openEnd } = slice2;
  while (openStart > 1 && openEnd > 1 && content3.childCount == 1 && content3.firstChild.childCount == 1) {
    openStart--;
    openEnd--;
    let node2 = content3.firstChild;
    context.push(node2.type.name, node2.attrs != node2.type.defaultAttrs ? node2.attrs : null);
    content3 = node2.content;
  }
  let serializer = view.someProp("clipboardSerializer") || DOMSerializer.fromSchema(view.state.schema);
  let doc3 = detachedDoc(), wrap2 = doc3.createElement("div");
  wrap2.appendChild(serializer.serializeFragment(content3, { document: doc3 }));
  let firstChild = wrap2.firstChild, needsWrap, wrappers = 0;
  while (firstChild && isElt(firstChild) && (needsWrap = wrapMap[firstChild.nodeName.toLowerCase()])) {
    for (let i2 = needsWrap.length - 1; i2 >= 0; i2--) {
      let wrapper = doc3.createElement(needsWrap[i2]);
      while (wrap2.firstChild)
        wrapper.appendChild(wrap2.firstChild);
      wrap2.appendChild(wrapper);
      wrappers++;
    }
    firstChild = wrap2.firstChild;
  }
  if (firstChild && isElt(firstChild))
    firstChild.setAttribute("data-pm-slice", `${openStart} ${openEnd}${wrappers ? ` -${wrappers}` : ""} ${JSON.stringify(context)}`);
  let text4 = view.someProp("clipboardTextSerializer", (f) => f(slice2, view)) || slice2.content.textBetween(0, slice2.content.size, "\n\n");
  return { dom: wrap2, text: text4, slice: slice2 };
}
function parseFromClipboard(view, text4, html2, plainText, $context) {
  let inCode = $context.parent.type.spec.code;
  let dom, slice2;
  if (!html2 && !text4)
    return null;
  let asText = !!text4 && (plainText || inCode || !html2);
  if (asText) {
    view.someProp("transformPastedText", (f) => {
      text4 = f(text4, inCode || plainText, view);
    });
    if (inCode) {
      slice2 = new Slice(Fragment.from(view.state.schema.text(text4.replace(/\r\n?/g, "\n"))), 0, 0);
      view.someProp("transformPasted", (f) => {
        slice2 = f(slice2, view, true);
      });
      return slice2;
    }
    let parsed = view.someProp("clipboardTextParser", (f) => f(text4, $context, plainText, view));
    if (parsed) {
      slice2 = parsed;
    } else {
      let marks = $context.marks();
      let { schema: schema2 } = view.state, serializer = DOMSerializer.fromSchema(schema2);
      dom = document.createElement("div");
      text4.split(/(?:\r\n?|\n)+/).forEach((block) => {
        let p = dom.appendChild(document.createElement("p"));
        if (block)
          p.appendChild(serializer.serializeNode(schema2.text(block, marks)));
      });
    }
  } else {
    view.someProp("transformPastedHTML", (f) => {
      html2 = f(html2, view);
    });
    dom = readHTML(html2);
    if (webkit)
      restoreReplacedSpaces(dom);
  }
  let contextNode = dom && dom.querySelector("[data-pm-slice]");
  let sliceData = contextNode && /^(\d+) (\d+)(?: -(\d+))? (.*)/.exec(contextNode.getAttribute("data-pm-slice") || "");
  if (sliceData && sliceData[3])
    for (let i2 = +sliceData[3]; i2 > 0; i2--) {
      let child = dom.firstChild;
      while (child && !isElt(child))
        child = child.nextSibling;
      if (!child)
        break;
      dom = child;
    }
  if (!slice2) {
    let parser = view.someProp("clipboardParser") || view.someProp("domParser") || DOMParser.fromSchema(view.state.schema);
    slice2 = parser.parseSlice(dom, {
      preserveWhitespace: !!(asText || sliceData),
      context: $context,
      ruleFromNode(dom2) {
        if (dom2.nodeName == "BR" && !dom2.nextSibling && dom2.parentNode && !inlineParents.test(dom2.parentNode.nodeName))
          return { ignore: true };
        return null;
      }
    });
  }
  if (sliceData) {
    slice2 = addContext(closeSlice(slice2, +sliceData[1], +sliceData[2]), sliceData[4]);
  } else {
    slice2 = Slice.maxOpen(normalizeSiblings(slice2.content, $context), true);
    if (slice2.openStart || slice2.openEnd) {
      let openStart = 0, openEnd = 0;
      for (let node2 = slice2.content.firstChild; openStart < slice2.openStart && !node2.type.spec.isolating; openStart++, node2 = node2.firstChild) {
      }
      for (let node2 = slice2.content.lastChild; openEnd < slice2.openEnd && !node2.type.spec.isolating; openEnd++, node2 = node2.lastChild) {
      }
      slice2 = closeSlice(slice2, openStart, openEnd);
    }
  }
  view.someProp("transformPasted", (f) => {
    slice2 = f(slice2, view, asText);
  });
  return slice2;
}
var inlineParents = /^(a|abbr|acronym|b|cite|code|del|em|i|ins|kbd|label|output|q|ruby|s|samp|span|strong|sub|sup|time|u|tt|var)$/i;
function normalizeSiblings(fragment, $context) {
  if (fragment.childCount < 2)
    return fragment;
  for (let d = $context.depth; d >= 0; d--) {
    let parent = $context.node(d);
    let match = parent.contentMatchAt($context.index(d));
    let lastWrap, result = [];
    fragment.forEach((node2) => {
      if (!result)
        return;
      let wrap2 = match.findWrapping(node2.type), inLast;
      if (!wrap2)
        return result = null;
      if (inLast = result.length && lastWrap.length && addToSibling(wrap2, lastWrap, node2, result[result.length - 1], 0)) {
        result[result.length - 1] = inLast;
      } else {
        if (result.length)
          result[result.length - 1] = closeRight(result[result.length - 1], lastWrap.length);
        let wrapped = withWrappers(node2, wrap2);
        result.push(wrapped);
        match = match.matchType(wrapped.type);
        lastWrap = wrap2;
      }
    });
    if (result)
      return Fragment.from(result);
  }
  return fragment;
}
function withWrappers(node2, wrap2, from2 = 0) {
  for (let i2 = wrap2.length - 1; i2 >= from2; i2--)
    node2 = wrap2[i2].create(null, Fragment.from(node2));
  return node2;
}
function addToSibling(wrap2, lastWrap, node2, sibling, depth) {
  if (depth < wrap2.length && depth < lastWrap.length && wrap2[depth] == lastWrap[depth]) {
    let inner = addToSibling(wrap2, lastWrap, node2, sibling.lastChild, depth + 1);
    if (inner)
      return sibling.copy(sibling.content.replaceChild(sibling.childCount - 1, inner));
    let match = sibling.contentMatchAt(sibling.childCount);
    if (match.matchType(depth == wrap2.length - 1 ? node2.type : wrap2[depth + 1]))
      return sibling.copy(sibling.content.append(Fragment.from(withWrappers(node2, wrap2, depth + 1))));
  }
}
function closeRight(node2, depth) {
  if (depth == 0)
    return node2;
  let fragment = node2.content.replaceChild(node2.childCount - 1, closeRight(node2.lastChild, depth - 1));
  let fill = node2.contentMatchAt(node2.childCount).fillBefore(Fragment.empty, true);
  return node2.copy(fragment.append(fill));
}
function closeRange(fragment, side, from2, to, depth, openEnd) {
  let node2 = side < 0 ? fragment.firstChild : fragment.lastChild, inner = node2.content;
  if (fragment.childCount > 1)
    openEnd = 0;
  if (depth < to - 1)
    inner = closeRange(inner, side, from2, to, depth + 1, openEnd);
  if (depth >= from2)
    inner = side < 0 ? node2.contentMatchAt(0).fillBefore(inner, openEnd <= depth).append(inner) : inner.append(node2.contentMatchAt(node2.childCount).fillBefore(Fragment.empty, true));
  return fragment.replaceChild(side < 0 ? 0 : fragment.childCount - 1, node2.copy(inner));
}
function closeSlice(slice2, openStart, openEnd) {
  if (openStart < slice2.openStart)
    slice2 = new Slice(closeRange(slice2.content, -1, openStart, slice2.openStart, 0, slice2.openEnd), openStart, slice2.openEnd);
  if (openEnd < slice2.openEnd)
    slice2 = new Slice(closeRange(slice2.content, 1, openEnd, slice2.openEnd, 0, 0), slice2.openStart, openEnd);
  return slice2;
}
var wrapMap = {
  thead: ["table"],
  tbody: ["table"],
  tfoot: ["table"],
  caption: ["table"],
  colgroup: ["table"],
  col: ["table", "colgroup"],
  tr: ["table", "tbody"],
  td: ["table", "tbody", "tr"],
  th: ["table", "tbody", "tr"]
};
function detachedDoc() {
  return document.implementation.createHTMLDocument("title");
}
var _policy = null;
function maybeWrapTrusted(html2) {
  let trustedTypes = window.trustedTypes;
  if (!trustedTypes)
    return html2;
  if (!_policy) {
    if (_policy = trustedTypes.defaultPolicy)
      try {
        return _policy.createHTML(html2);
      } catch (_a) {
      }
    _policy = trustedTypes.createPolicy("ProseMirrorClipboard", { createHTML: (s) => s });
  }
  return _policy.createHTML(html2);
}
function readHTML(html2) {
  let metas = /^(\s*<meta [^>]*>)*/.exec(html2);
  if (metas)
    html2 = html2.slice(metas[0].length);
  let doc3 = detachedDoc(), elt = doc3.body;
  let firstTag = /<([a-z][^>\s]+)/i.exec(html2), wrap2;
  if (wrap2 = firstTag && wrapMap[firstTag[1].toLowerCase()])
    html2 = wrap2.map((n) => "<" + n + ">").join("") + html2 + wrap2.map((n) => "</" + n + ">").reverse().join("");
  elt.innerHTML = maybeWrapTrusted(html2);
  if (wrap2)
    for (let i2 = 0; i2 < wrap2.length; i2++)
      elt = elt.querySelector(wrap2[i2]) || elt;
  for (let i2 = 0; i2 < doc3.styleSheets.length; i2++) {
    let style = doc3.styleSheets[i2];
    for (let j = 0; j < style.rules.length; j++) {
      let rule = style.rules[j];
      if (rule instanceof CSSStyleRule) {
        let matches2 = elt.querySelectorAll(rule.selectorText);
        for (let k = 0; k < matches2.length; k++)
          matches2[k].style.cssText += rule.style.cssText;
      }
    }
  }
  return elt;
}
function restoreReplacedSpaces(dom) {
  let nodes = dom.querySelectorAll(chrome ? "span:not([class]):not([style])" : "span.Apple-converted-space");
  for (let i2 = 0; i2 < nodes.length; i2++) {
    let node2 = nodes[i2];
    if (node2.childNodes.length == 1 && node2.textContent == " " && node2.parentNode)
      node2.parentNode.replaceChild(dom.ownerDocument.createTextNode(" "), node2);
  }
}
function addContext(slice2, context) {
  if (!slice2.size)
    return slice2;
  let schema2 = slice2.content.firstChild.type.schema, array;
  try {
    array = JSON.parse(context);
  } catch (e) {
    return slice2;
  }
  let { content: content3, openStart, openEnd } = slice2;
  for (let i2 = array.length - 2; i2 >= 0; i2 -= 2) {
    let type = schema2.nodes[array[i2]];
    if (!type || type.hasRequiredAttrs())
      break;
    try {
      content3 = Fragment.from(type.create(array[i2 + 1], content3));
    } catch (e) {
      break;
    }
    openStart++;
    openEnd++;
  }
  return new Slice(content3, openStart, openEnd);
}
var handlers = {};
var editHandlers = {};
var passiveHandlers = { touchstart: true, touchmove: true };
var InputState = class {
  constructor() {
    this.shiftKey = false;
    this.mouseDown = null;
    this.lastKeyCode = null;
    this.lastKeyCodeTime = 0;
    this.lastClick = { time: 0, x: 0, y: 0, type: "", button: 0 };
    this.lastSelectionOrigin = null;
    this.lastSelectionTime = 0;
    this.lastIOSEnter = 0;
    this.lastIOSEnterFallbackTimeout = -1;
    this.lastFocus = 0;
    this.lastTouch = 0;
    this.lastChromeDelete = 0;
    this.composing = false;
    this.compositionNode = null;
    this.composingTimeout = -1;
    this.compositionNodes = [];
    this.compositionEndedAt = -2e8;
    this.compositionID = 1;
    this.badSafariComposition = false;
    this.compositionPendingChanges = 0;
    this.domChangeCount = 0;
    this.eventHandlers = /* @__PURE__ */ Object.create(null);
    this.hideSelectionGuard = null;
  }
};
function initInput(view) {
  for (let event in handlers) {
    let handler = handlers[event];
    view.dom.addEventListener(event, view.input.eventHandlers[event] = (event2) => {
      if (eventBelongsToView(view, event2) && !runCustomHandler(view, event2) && (view.editable || !(event2.type in editHandlers)))
        handler(view, event2);
    }, passiveHandlers[event] ? { passive: true } : void 0);
  }
  if (safari)
    view.dom.addEventListener("input", () => null);
  ensureListeners(view);
}
function setSelectionOrigin(view, origin) {
  view.input.lastSelectionOrigin = origin;
  view.input.lastSelectionTime = Date.now();
}
function destroyInput(view) {
  if (view.input.mouseDown)
    view.input.mouseDown.done();
  view.domObserver.stop();
  for (let type in view.input.eventHandlers)
    view.dom.removeEventListener(type, view.input.eventHandlers[type]);
  clearTimeout(view.input.composingTimeout);
  clearTimeout(view.input.lastIOSEnterFallbackTimeout);
}
function ensureListeners(view) {
  view.someProp("handleDOMEvents", (currentHandlers) => {
    for (let type in currentHandlers)
      if (!view.input.eventHandlers[type])
        view.dom.addEventListener(type, view.input.eventHandlers[type] = (event) => runCustomHandler(view, event));
  });
}
function runCustomHandler(view, event) {
  return view.someProp("handleDOMEvents", (handlers2) => {
    let handler = handlers2[event.type];
    return handler ? handler(view, event) || event.defaultPrevented : false;
  });
}
function eventBelongsToView(view, event) {
  if (!event.bubbles)
    return true;
  if (event.defaultPrevented)
    return false;
  for (let node2 = event.target; node2 != view.dom; node2 = node2.parentNode)
    if (!node2 || node2.nodeType == 11 || node2.pmViewDesc && node2.pmViewDesc.stopEvent(event))
      return false;
  return true;
}
function dispatchEvent(view, event) {
  if (!runCustomHandler(view, event) && handlers[event.type] && (view.editable || !(event.type in editHandlers)))
    handlers[event.type](view, event);
}
editHandlers.keydown = (view, _event) => {
  let event = _event;
  view.input.shiftKey = event.keyCode == 16 || event.shiftKey;
  if (inOrNearComposition(view))
    return;
  view.input.lastKeyCode = event.keyCode;
  view.input.lastKeyCodeTime = Date.now();
  if (android && chrome && event.keyCode == 13)
    return;
  if (event.keyCode != 229)
    view.domObserver.forceFlush();
  if (ios && event.keyCode == 13 && !event.ctrlKey && !event.altKey && !event.metaKey) {
    let now = Date.now();
    view.input.lastIOSEnter = now;
    view.input.lastIOSEnterFallbackTimeout = setTimeout(() => {
      if (view.input.lastIOSEnter == now) {
        view.someProp("handleKeyDown", (f) => f(view, keyEvent(13, "Enter")));
        view.input.lastIOSEnter = 0;
      }
    }, 200);
  } else if (view.someProp("handleKeyDown", (f) => f(view, event)) || captureKeyDown(view, event)) {
    event.preventDefault();
  } else {
    setSelectionOrigin(view, "key");
  }
};
editHandlers.keyup = (view, event) => {
  if (event.keyCode == 16)
    view.input.shiftKey = false;
};
editHandlers.keypress = (view, _event) => {
  let event = _event;
  if (inOrNearComposition(view) || !event.charCode || event.ctrlKey && !event.altKey || mac && event.metaKey)
    return;
  if (view.someProp("handleKeyPress", (f) => f(view, event))) {
    event.preventDefault();
    return;
  }
  let sel = view.state.selection;
  if (!(sel instanceof TextSelection) || !sel.$from.sameParent(sel.$to)) {
    let text4 = String.fromCharCode(event.charCode);
    let deflt = () => view.state.tr.insertText(text4).scrollIntoView();
    if (!/[\r\n]/.test(text4) && !view.someProp("handleTextInput", (f) => f(view, sel.$from.pos, sel.$to.pos, text4, deflt)))
      view.dispatch(deflt());
    event.preventDefault();
  }
};
function eventCoords(event) {
  return { left: event.clientX, top: event.clientY };
}
function isNear(event, click) {
  let dx = click.x - event.clientX, dy = click.y - event.clientY;
  return dx * dx + dy * dy < 100;
}
function runHandlerOnContext(view, propName, pos, inside, event) {
  if (inside == -1)
    return false;
  let $pos = view.state.doc.resolve(inside);
  for (let i2 = $pos.depth + 1; i2 > 0; i2--) {
    if (view.someProp(propName, (f) => i2 > $pos.depth ? f(view, pos, $pos.nodeAfter, $pos.before(i2), event, true) : f(view, pos, $pos.node(i2), $pos.before(i2), event, false)))
      return true;
  }
  return false;
}
function updateSelection(view, selection, origin) {
  if (!view.focused)
    view.focus();
  if (view.state.selection.eq(selection))
    return;
  let tr = view.state.tr.setSelection(selection);
  tr.setMeta("pointer", true);
  view.dispatch(tr);
}
function selectClickedLeaf(view, inside) {
  if (inside == -1)
    return false;
  let $pos = view.state.doc.resolve(inside), node2 = $pos.nodeAfter;
  if (node2 && node2.isAtom && NodeSelection.isSelectable(node2)) {
    updateSelection(view, new NodeSelection($pos));
    return true;
  }
  return false;
}
function selectClickedNode(view, inside) {
  if (inside == -1)
    return false;
  let sel = view.state.selection, selectedNode, selectAt;
  if (sel instanceof NodeSelection)
    selectedNode = sel.node;
  let $pos = view.state.doc.resolve(inside);
  for (let i2 = $pos.depth + 1; i2 > 0; i2--) {
    let node2 = i2 > $pos.depth ? $pos.nodeAfter : $pos.node(i2);
    if (NodeSelection.isSelectable(node2)) {
      if (selectedNode && sel.$from.depth > 0 && i2 >= sel.$from.depth && $pos.before(sel.$from.depth + 1) == sel.$from.pos)
        selectAt = $pos.before(sel.$from.depth);
      else
        selectAt = $pos.before(i2);
      break;
    }
  }
  if (selectAt != null) {
    updateSelection(view, NodeSelection.create(view.state.doc, selectAt));
    return true;
  } else {
    return false;
  }
}
function handleSingleClick(view, pos, inside, event, selectNode) {
  return runHandlerOnContext(view, "handleClickOn", pos, inside, event) || view.someProp("handleClick", (f) => f(view, pos, event)) || (selectNode ? selectClickedNode(view, inside) : selectClickedLeaf(view, inside));
}
function handleDoubleClick(view, pos, inside, event) {
  return runHandlerOnContext(view, "handleDoubleClickOn", pos, inside, event) || view.someProp("handleDoubleClick", (f) => f(view, pos, event));
}
function handleTripleClick(view, pos, inside, event) {
  return runHandlerOnContext(view, "handleTripleClickOn", pos, inside, event) || view.someProp("handleTripleClick", (f) => f(view, pos, event)) || defaultTripleClick(view, inside, event);
}
function defaultTripleClick(view, inside, event) {
  if (event.button != 0)
    return false;
  let selection = selectionForTripleClick(view, inside, true), doc3 = view.state.doc;
  if (!selection)
    return false;
  updateSelection(view, selection);
  if (selection instanceof TextSelection && doc3.eq(view.state.doc))
    view.input.mouseDown = new TripleClickDrag(view, selection);
  return true;
}
function selectionForTripleClick(view, inside, selectNodes) {
  let doc3 = view.state.doc;
  if (inside == -1)
    return doc3.inlineContent ? TextSelection.create(doc3, 0, doc3.content.size) : null;
  let $pos = doc3.resolve(inside);
  for (let i2 = $pos.depth + 1; i2 > 0; i2--) {
    let node2 = i2 > $pos.depth ? $pos.nodeAfter : $pos.node(i2);
    let nodePos = $pos.before(i2);
    if (node2.inlineContent)
      return TextSelection.create(doc3, nodePos + 1, nodePos + 1 + node2.content.size);
    else if (selectNodes && NodeSelection.isSelectable(node2))
      return NodeSelection.create(doc3, nodePos);
  }
  return null;
}
function forceDOMFlush(view) {
  return endComposition(view);
}
var selectNodeModifier = mac ? "metaKey" : "ctrlKey";
handlers.mousedown = (view, _event) => {
  let event = _event;
  view.input.shiftKey = event.shiftKey;
  let flushed = forceDOMFlush(view);
  let now = Date.now(), type = "singleClick";
  if (now - view.input.lastClick.time < 500 && isNear(event, view.input.lastClick) && !event[selectNodeModifier] && view.input.lastClick.button == event.button) {
    if (view.input.lastClick.type == "singleClick")
      type = "doubleClick";
    else if (view.input.lastClick.type == "doubleClick")
      type = "tripleClick";
  }
  view.input.lastClick = { time: now, x: event.clientX, y: event.clientY, type, button: event.button };
  if (view.input.mouseDown)
    view.input.mouseDown.done();
  let pos = view.posAtCoords(eventCoords(event));
  if (!pos)
    return;
  if (type == "singleClick") {
    view.input.mouseDown = new LeftMouseDown(view, pos, event, !!flushed);
  } else if ((type == "doubleClick" ? handleDoubleClick : handleTripleClick)(view, pos.pos, pos.inside, event)) {
    event.preventDefault();
  } else {
    setSelectionOrigin(view, "pointer");
  }
};
var MouseDown = class {
  constructor(view) {
    this.view = view;
    this.mightDrag = null;
    view.root.addEventListener("mouseup", this.up = this.up.bind(this));
    view.root.addEventListener("mousemove", this.move = this.move.bind(this));
  }
  up(event) {
    this.done();
  }
  move(event) {
    if (event.buttons == 0)
      this.done();
  }
  done() {
    this.view.root.removeEventListener("mouseup", this.up);
    this.view.root.removeEventListener("mousemove", this.move);
    if (this.view.input.mouseDown == this)
      this.view.input.mouseDown = null;
  }
  delaySelUpdate() {
    return false;
  }
};
var LeftMouseDown = class extends MouseDown {
  constructor(view, pos, event, flushed) {
    super(view);
    this.pos = pos;
    this.event = event;
    this.flushed = flushed;
    this.delayedSelectionSync = false;
    this.startDoc = view.state.doc;
    this.selectNode = !!event[selectNodeModifier];
    this.allowDefault = event.shiftKey;
    let targetNode, targetPos;
    if (pos.inside > -1) {
      targetNode = view.state.doc.nodeAt(pos.inside);
      targetPos = pos.inside;
    } else {
      let $pos = view.state.doc.resolve(pos.pos);
      targetNode = $pos.parent;
      targetPos = $pos.depth ? $pos.before() : 0;
    }
    const target = flushed ? null : event.target;
    const targetDesc = target ? view.docView.nearestDesc(target, true) : null;
    this.target = targetDesc && isElt(targetDesc.nodeDOM) ? targetDesc.nodeDOM : null;
    let { selection } = view.state;
    if (event.button == 0 && (targetNode.type.spec.draggable && targetNode.type.spec.selectable !== false || selection instanceof NodeSelection && selection.from <= targetPos && selection.to > targetPos))
      this.mightDrag = {
        node: targetNode,
        pos: targetPos,
        addAttr: !!(this.target && !this.target.draggable),
        setUneditable: !!(this.target && gecko && !this.target.hasAttribute("contentEditable"))
      };
    if (this.target && this.mightDrag && (this.mightDrag.addAttr || this.mightDrag.setUneditable)) {
      this.view.domObserver.stop();
      if (this.mightDrag.addAttr)
        this.target.draggable = true;
      if (this.mightDrag.setUneditable)
        setTimeout(() => {
          if (this.view.input.mouseDown == this)
            this.target.setAttribute("contentEditable", "false");
        }, 20);
      this.view.domObserver.start();
    }
    setSelectionOrigin(view, "pointer");
  }
  done() {
    super.done();
    if (this.mightDrag && this.target) {
      this.view.domObserver.stop();
      if (this.mightDrag.addAttr)
        this.target.removeAttribute("draggable");
      if (this.mightDrag.setUneditable)
        this.target.removeAttribute("contentEditable");
      this.view.domObserver.start();
    }
    if (this.delayedSelectionSync)
      setTimeout(() => {
        if (!this.view.isDestroyed)
          selectionToDOM(this.view);
      });
  }
  up(event) {
    this.done();
    if (!this.view.dom.contains(event.target))
      return;
    let pos = this.pos;
    if (this.view.state.doc != this.startDoc)
      pos = this.view.posAtCoords(eventCoords(event));
    this.updateAllowDefault(event);
    if (this.allowDefault || !pos) {
      setSelectionOrigin(this.view, "pointer");
    } else if (handleSingleClick(this.view, pos.pos, pos.inside, event, this.selectNode)) {
      event.preventDefault();
    } else if (event.button == 0 && (this.flushed || // Safari ignores clicks on draggable elements
    safari && this.mightDrag && !this.mightDrag.node.isAtom || // Chrome will sometimes treat a node selection as a
    // cursor, but still report that the node is selected
    // when asked through getSelection. You'll then get a
    // situation where clicking at the point where that
    // (hidden) cursor is doesn't change the selection, and
    // thus doesn't get a reaction from ProseMirror. This
    // works around that.
    chrome && !this.view.state.selection.visible && Math.min(Math.abs(pos.pos - this.view.state.selection.from), Math.abs(pos.pos - this.view.state.selection.to)) <= 2)) {
      updateSelection(this.view, Selection.near(this.view.state.doc.resolve(pos.pos)));
      event.preventDefault();
    } else {
      setSelectionOrigin(this.view, "pointer");
    }
  }
  move(event) {
    this.updateAllowDefault(event);
    setSelectionOrigin(this.view, "pointer");
    super.move(event);
  }
  updateAllowDefault(event) {
    if (!this.allowDefault && (Math.abs(this.event.x - event.clientX) > 4 || Math.abs(this.event.y - event.clientY) > 4))
      this.allowDefault = true;
  }
  delaySelUpdate() {
    if (!this.allowDefault)
      return false;
    this.delayedSelectionSync = true;
    return true;
  }
};
var TripleClickDrag = class extends MouseDown {
  constructor(view, startSelection) {
    super(view);
    this.startSelection = startSelection;
    this.startDoc = view.state.doc;
  }
  move(event) {
    if (event.buttons == 0 || this.view.isDestroyed || !this.view.state.doc.eq(this.startDoc)) {
      this.done();
      return;
    }
    event.preventDefault();
    setSelectionOrigin(this.view, "pointer");
    let pos = this.view.posAtCoords(eventCoords(event));
    let target = pos && selectionForTripleClick(this.view, pos.inside, false);
    if (!target)
      return;
    let { doc: doc3 } = this.view.state, start = this.startSelection;
    let [anchor, head] = target.from < start.from ? [start.to, target.from] : [start.from, target.to];
    updateSelection(this.view, TextSelection.create(doc3, anchor, head));
  }
};
handlers.touchstart = (view) => {
  view.input.lastTouch = Date.now();
  forceDOMFlush(view);
  setSelectionOrigin(view, "pointer");
};
handlers.touchmove = (view) => {
  view.input.lastTouch = Date.now();
  setSelectionOrigin(view, "pointer");
};
handlers.contextmenu = (view) => forceDOMFlush(view);
function inOrNearComposition(view, event) {
  if (view.composing)
    return true;
  if (safari && Math.abs(Date.now() - view.input.compositionEndedAt) < 500) {
    view.input.compositionEndedAt = -2e8;
    return true;
  }
  return false;
}
var timeoutComposition = android ? 5e3 : -1;
editHandlers.compositionstart = editHandlers.compositionupdate = (view) => {
  if (!view.composing) {
    view.domObserver.flush();
    let { state } = view, $pos = state.selection.$to;
    if (state.selection instanceof TextSelection && state.selection.empty && (state.storedMarks || !$pos.textOffset && $pos.parentOffset && $pos.nodeBefore.marks.some((m) => m.type.spec.inclusive === false) || chrome && windows && selectionBeforeUneditable(view))) {
      view.markCursor = view.state.storedMarks || $pos.marks();
      endComposition(view, true);
      view.markCursor = null;
    } else {
      endComposition(view, !state.selection.empty);
      if (gecko && state.selection.empty && $pos.parentOffset && !$pos.textOffset && $pos.nodeBefore.marks.length) {
        let sel = view.domSelectionRange();
        for (let node2 = sel.focusNode, offset = sel.focusOffset; node2 && isElt(node2) && offset != 0; ) {
          let before = offset < 0 ? node2.lastChild : node2.childNodes[offset - 1];
          if (!before)
            break;
          if (isText(before)) {
            let sel2 = view.domSelection();
            if (sel2)
              sel2.collapse(before, before.nodeValue.length);
            break;
          } else {
            node2 = before;
            offset = -1;
          }
        }
      }
    }
    view.input.composing = true;
  }
  scheduleComposeEnd(view, timeoutComposition);
};
function selectionBeforeUneditable(view) {
  let { focusNode, focusOffset } = view.domSelectionRange();
  if (!focusNode || !isElt(focusNode) || focusOffset >= focusNode.childNodes.length)
    return false;
  let next = focusNode.childNodes[focusOffset];
  return isElt(next) && next.contentEditable == "false";
}
editHandlers.compositionend = (view, event) => {
  if (view.composing) {
    view.input.composing = false;
    view.input.compositionEndedAt = Date.now();
    view.input.compositionPendingChanges = view.domObserver.pendingRecords().length ? view.input.compositionID : 0;
    view.input.compositionNode = null;
    if (view.input.badSafariComposition)
      view.domObserver.forceFlush();
    else if (view.input.compositionPendingChanges)
      Promise.resolve().then(() => view.domObserver.flush());
    view.input.compositionID++;
    scheduleComposeEnd(view, 20);
  }
};
function scheduleComposeEnd(view, delay) {
  clearTimeout(view.input.composingTimeout);
  if (delay > -1)
    view.input.composingTimeout = setTimeout(() => endComposition(view), delay);
}
function clearComposition(view) {
  if (view.composing) {
    view.input.composing = false;
    view.input.compositionEndedAt = Date.now();
  }
  while (view.input.compositionNodes.length > 0)
    view.input.compositionNodes.pop().markParentsDirty();
}
function findCompositionNode(view) {
  let sel = view.domSelectionRange();
  if (!sel.focusNode)
    return null;
  let textBefore = textNodeBefore$1(sel.focusNode, sel.focusOffset);
  let textAfter = textNodeAfter$1(sel.focusNode, sel.focusOffset);
  if (textBefore && textAfter && textBefore != textAfter) {
    let descAfter = textAfter.pmViewDesc, lastChanged = view.domObserver.lastChangedTextNode;
    if (textBefore == lastChanged || textAfter == lastChanged)
      return lastChanged;
    if (!descAfter || !descAfter.isText(textAfter.nodeValue)) {
      return textAfter;
    } else if (view.input.compositionNode == textAfter) {
      let descBefore = textBefore.pmViewDesc;
      if (!(!descBefore || !descBefore.isText(textBefore.nodeValue)))
        return textAfter;
    }
  }
  return textBefore || textAfter;
}
function endComposition(view, restarting = false) {
  if (android && view.domObserver.flushingSoon >= 0)
    return;
  view.domObserver.forceFlush();
  clearComposition(view);
  if (restarting || view.docView && view.docView.dirty) {
    let sel = selectionFromDOM(view), cur = view.state.selection;
    if (sel && !sel.eq(cur))
      view.dispatch(view.state.tr.setSelection(sel));
    else if ((view.markCursor || restarting) && !cur.$from.node(cur.$from.sharedDepth(cur.to)).inlineContent)
      view.dispatch(view.state.tr.deleteSelection());
    else
      view.updateState(view.state);
    return true;
  }
  return false;
}
function captureCopy(view, dom) {
  if (!view.dom.parentNode)
    return;
  let wrap2 = view.dom.parentNode.appendChild(document.createElement("div"));
  wrap2.appendChild(dom);
  wrap2.style.cssText = "position: fixed; left: -10000px; top: 10px";
  let sel = getSelection(), range = document.createRange();
  range.selectNodeContents(dom);
  view.dom.blur();
  sel.removeAllRanges();
  sel.addRange(range);
  setTimeout(() => {
    if (wrap2.parentNode)
      wrap2.parentNode.removeChild(wrap2);
    view.focus();
  }, 50);
}
var brokenClipboardAPI = ie && ie_version < 15 || ios && webkit_version < 604;
handlers.copy = editHandlers.cut = (view, _event) => {
  let event = _event;
  let sel = view.state.selection, cut = event.type == "cut";
  if (sel.empty)
    return;
  let data = brokenClipboardAPI ? null : event.clipboardData;
  let slice2 = sel.content(), { dom, text: text4 } = serializeForClipboard(view, slice2);
  if (data) {
    event.preventDefault();
    data.clearData();
    data.setData("text/html", dom.innerHTML);
    data.setData("text/plain", text4);
  } else {
    captureCopy(view, dom);
  }
  if (cut)
    view.dispatch(view.state.tr.deleteSelection().scrollIntoView().setMeta("uiEvent", "cut"));
};
function sliceSingleNode(slice2) {
  return slice2.openStart == 0 && slice2.openEnd == 0 && slice2.content.childCount == 1 ? slice2.content.firstChild : null;
}
function capturePaste(view, event) {
  if (!view.dom.parentNode)
    return;
  let plainText = view.input.shiftKey || view.state.selection.$from.parent.type.spec.code;
  let target = view.dom.parentNode.appendChild(document.createElement(plainText ? "textarea" : "div"));
  if (!plainText)
    target.contentEditable = "true";
  target.style.cssText = "position: fixed; left: -10000px; top: 10px";
  target.focus();
  let plain = view.input.shiftKey && view.input.lastKeyCode != 45;
  setTimeout(() => {
    view.focus();
    if (target.parentNode)
      target.parentNode.removeChild(target);
    if (plainText)
      doPaste(view, target.value, null, plain, event);
    else
      doPaste(view, target.textContent, target.innerHTML, plain, event);
  }, 50);
}
function doPaste(view, text4, html2, preferPlain, event) {
  let slice2 = parseFromClipboard(view, text4, html2, preferPlain, view.state.selection.$from);
  if (view.someProp("handlePaste", (f) => f(view, event, slice2 || Slice.empty)))
    return true;
  if (!slice2)
    return false;
  let singleNode = sliceSingleNode(slice2);
  let tr = singleNode ? view.state.tr.replaceSelectionWith(singleNode, preferPlain) : view.state.tr.replaceSelection(slice2);
  view.dispatch(tr.scrollIntoView().setMeta("paste", true).setMeta("uiEvent", "paste"));
  return true;
}
function getText(clipboardData) {
  let text4 = clipboardData.getData("text/plain") || clipboardData.getData("Text");
  if (text4)
    return text4;
  let uris = clipboardData.getData("text/uri-list");
  return uris ? uris.replace(/\r?\n/g, " ") : "";
}
editHandlers.paste = (view, _event) => {
  let event = _event;
  if (view.composing && !android)
    return;
  let data = brokenClipboardAPI ? null : event.clipboardData;
  let plain = view.input.shiftKey && view.input.lastKeyCode != 45;
  if (data && doPaste(view, getText(data), data.getData("text/html"), plain, event))
    event.preventDefault();
  else
    capturePaste(view, event);
};
var Dragging = class {
  constructor(slice2, move, node2) {
    this.slice = slice2;
    this.move = move;
    this.node = node2;
  }
};
var dragCopyModifier = mac ? "altKey" : "ctrlKey";
function dragMoves(view, event) {
  let copy2;
  view.someProp("dragCopies", (test) => {
    copy2 = copy2 || test(event);
  });
  return copy2 != null ? !copy2 : !event[dragCopyModifier];
}
handlers.dragstart = (view, _event) => {
  let event = _event;
  let mouseDown = view.input.mouseDown;
  if (mouseDown)
    mouseDown.done();
  if (!event.dataTransfer)
    return;
  let sel = view.state.selection;
  let pos = sel.empty ? null : view.posAtCoords(eventCoords(event));
  let node2;
  if (pos && pos.pos >= sel.from && pos.pos <= (sel instanceof NodeSelection ? sel.to - 1 : sel.to)) ;
  else if (mouseDown && mouseDown.mightDrag) {
    node2 = NodeSelection.create(view.state.doc, mouseDown.mightDrag.pos);
  } else if (event.target && isElt(event.target)) {
    let desc = view.docView.nearestDesc(event.target, true);
    if (desc && desc.node.type.spec.draggable && desc != view.docView)
      node2 = NodeSelection.create(view.state.doc, desc.posBefore);
  }
  let draggedSlice = (node2 || view.state.selection).content();
  let { dom, text: text4, slice: slice2 } = serializeForClipboard(view, draggedSlice);
  if (!event.dataTransfer.files.length || !chrome || chrome_version > 120)
    event.dataTransfer.clearData();
  event.dataTransfer.setData(brokenClipboardAPI ? "Text" : "text/html", dom.innerHTML);
  event.dataTransfer.effectAllowed = "copyMove";
  if (!brokenClipboardAPI)
    event.dataTransfer.setData("text/plain", text4);
  view.dragging = new Dragging(slice2, dragMoves(view, event), node2);
};
handlers.dragend = (view) => {
  let dragging = view.dragging;
  window.setTimeout(() => {
    if (view.dragging == dragging)
      view.dragging = null;
  }, 50);
};
editHandlers.dragover = editHandlers.dragenter = (_, e) => e.preventDefault();
editHandlers.drop = (view, event) => {
  try {
    handleDrop(view, event, view.dragging);
  } finally {
    view.dragging = null;
  }
};
function handleDrop(view, event, dragging) {
  if (!event.dataTransfer)
    return;
  let eventPos = view.posAtCoords(eventCoords(event));
  if (!eventPos)
    return;
  let $mouse = view.state.doc.resolve(eventPos.pos);
  let slice2 = dragging && dragging.slice;
  if (slice2) {
    view.someProp("transformPasted", (f) => {
      slice2 = f(slice2, view, false);
    });
  } else {
    slice2 = parseFromClipboard(view, getText(event.dataTransfer), brokenClipboardAPI ? null : event.dataTransfer.getData("text/html"), false, $mouse);
  }
  let move = !!(dragging && dragMoves(view, event));
  if (view.someProp("handleDrop", (f) => f(view, event, slice2 || Slice.empty, move))) {
    event.preventDefault();
    return;
  }
  if (!slice2)
    return;
  event.preventDefault();
  let insertPos = slice2 ? dropPoint(view.state.doc, $mouse.pos, slice2) : $mouse.pos;
  if (insertPos == null)
    insertPos = $mouse.pos;
  let tr = view.state.tr;
  if (move) {
    let { node: node2 } = dragging;
    if (node2)
      node2.replace(tr);
    else
      tr.deleteSelection();
  }
  let pos = tr.mapping.map(insertPos);
  let isNode = slice2.openStart == 0 && slice2.openEnd == 0 && slice2.content.childCount == 1;
  let beforeInsert = tr.doc;
  if (isNode)
    tr.replaceRangeWith(pos, pos, slice2.content.firstChild);
  else
    tr.replaceRange(pos, pos, slice2);
  if (tr.doc.eq(beforeInsert))
    return;
  let $pos = tr.doc.resolve(pos);
  if (isNode && NodeSelection.isSelectable(slice2.content.firstChild) && $pos.nodeAfter && $pos.nodeAfter.sameMarkup(slice2.content.firstChild)) {
    tr.setSelection(new NodeSelection($pos));
  } else {
    let end = tr.mapping.map(insertPos);
    tr.mapping.maps[tr.mapping.maps.length - 1].forEach((_from, _to, _newFrom, newTo) => end = newTo);
    tr.setSelection(selectionBetween(view, $pos, tr.doc.resolve(end)));
  }
  view.focus();
  view.dispatch(tr.setMeta("uiEvent", "drop"));
}
handlers.focus = (view) => {
  view.input.lastFocus = Date.now();
  if (!view.focused) {
    view.domObserver.stop();
    view.dom.classList.add("ProseMirror-focused");
    view.domObserver.start();
    view.focused = true;
    setTimeout(() => {
      if (view.docView && view.hasFocus() && !view.domObserver.currentSelection.eq(view.domSelectionRange()))
        selectionToDOM(view);
    }, 20);
  }
};
handlers.blur = (view, _event) => {
  let event = _event;
  if (view.focused) {
    view.domObserver.stop();
    view.dom.classList.remove("ProseMirror-focused");
    view.domObserver.start();
    if (event.relatedTarget && view.dom.contains(event.relatedTarget))
      view.domObserver.currentSelection.clear();
    view.focused = false;
  }
};
handlers.beforeinput = (view, _event) => {
  let event = _event;
  if (android && event.inputType == "deleteContentBackward") {
    view.domObserver.flushSoon();
    let { domChangeCount } = view.input;
    setTimeout(() => {
      if (view.input.domChangeCount != domChangeCount)
        return;
      view.dom.blur();
      view.focus();
      if (view.someProp("handleKeyDown", (f) => f(view, keyEvent(8, "Backspace"))))
        return;
      let { $cursor } = view.state.selection;
      if ($cursor && $cursor.pos > 0)
        view.dispatch(view.state.tr.delete($cursor.pos - 1, $cursor.pos).scrollIntoView());
    }, 50);
  }
};
for (let prop in editHandlers)
  handlers[prop] = editHandlers[prop];
function compareObjs(a, b) {
  if (a == b)
    return true;
  for (let p in a)
    if (a[p] !== b[p])
      return false;
  for (let p in b)
    if (!(p in a))
      return false;
  return true;
}
var FragmentCursor = class {
  constructor(frag) {
    this.frag = frag;
    this.index = 0;
    this.off = 0;
  }
  nodeAt(off) {
    while (this.off <= off && this.index < this.frag.childCount) {
      let next = this.frag.child(this.index);
      if (this.off == off)
        return next;
      this.off += next.nodeSize;
      this.index++;
    }
    return null;
  }
};
var WidgetType = class _WidgetType {
  constructor(toDOM, spec) {
    this.toDOM = toDOM;
    this.spec = spec || noSpec;
    this.side = this.spec.side || 0;
  }
  map(mapping, span, offset, oldOffset) {
    let { pos, deleted } = mapping.mapResult(span.from + oldOffset, this.side < 0 ? -1 : 1);
    return deleted ? null : new Decoration(pos - offset, pos - offset, this);
  }
  valid() {
    return true;
  }
  eq(other) {
    return this == other || other instanceof _WidgetType && (this.spec.key && this.spec.key == other.spec.key || this.toDOM == other.toDOM && compareObjs(this.spec, other.spec));
  }
  destroy(node2) {
    if (this.spec.destroy)
      this.spec.destroy(node2);
  }
};
var InlineType = class _InlineType {
  constructor(attrs, spec) {
    this.attrs = attrs;
    this.spec = spec || noSpec;
  }
  map(mapping, span, offset, oldOffset) {
    let from2 = mapping.map(span.from + oldOffset, this.spec.inclusiveStart ? -1 : 1) - offset;
    let to = mapping.map(span.to + oldOffset, this.spec.inclusiveEnd ? 1 : -1) - offset;
    return from2 >= to ? null : new Decoration(from2, to, this);
  }
  valid(_, span) {
    return span.from < span.to;
  }
  eq(other) {
    return this == other || other instanceof _InlineType && compareObjs(this.attrs, other.attrs) && compareObjs(this.spec, other.spec);
  }
  static is(span) {
    return span.type instanceof _InlineType;
  }
  destroy() {
  }
};
var NodeType2 = class _NodeType {
  constructor(attrs, spec) {
    this.attrs = attrs;
    this.spec = spec || noSpec;
  }
  map(mapping, span, offset, oldOffset) {
    let from2 = mapping.mapResult(span.from + oldOffset, 1);
    if (from2.deleted)
      return null;
    let to = mapping.mapResult(span.to + oldOffset, -1);
    if (to.deleted || to.pos <= from2.pos)
      return null;
    return new Decoration(from2.pos - offset, to.pos - offset, this);
  }
  valid(node2, span, cursor) {
    let found2 = cursor.nodeAt(span.from);
    return !!found2 && !found2.isText && span.from + found2.nodeSize == span.to;
  }
  eq(other) {
    return this == other || other instanceof _NodeType && compareObjs(this.attrs, other.attrs) && compareObjs(this.spec, other.spec);
  }
  destroy() {
  }
};
var Decoration = class _Decoration {
  /**
  @internal
  */
  constructor(from2, to, type) {
    this.from = from2;
    this.to = to;
    this.type = type;
  }
  /**
  @internal
  */
  copy(from2, to) {
    return new _Decoration(from2, to, this.type);
  }
  /**
  @internal
  */
  eq(other, offset = 0) {
    return this.type.eq(other.type) && this.from + offset == other.from && this.to + offset == other.to;
  }
  /**
  @internal
  */
  map(mapping, offset, oldOffset) {
    return this.type.map(mapping, this, offset, oldOffset);
  }
  /**
  Creates a widget decoration, which is a DOM node that's shown in
  the document at the given position. It is recommended that you
  delay rendering the widget by passing a function that will be
  called when the widget is actually drawn in a view, but you can
  also directly pass a DOM node. `getPos` can be used to find the
  widget's current document position.
  */
  static widget(pos, toDOM, spec) {
    return new _Decoration(pos, pos, new WidgetType(toDOM, spec));
  }
  /**
  Creates an inline decoration, which adds the given attributes to
  each inline node between `from` and `to`.
  */
  static inline(from2, to, attrs, spec) {
    return new _Decoration(from2, to, new InlineType(attrs, spec));
  }
  /**
  Creates a node decoration. `from` and `to` should point precisely
  before and after a node in the document. That node, and only that
  node, will receive the given attributes.
  */
  static node(from2, to, attrs, spec) {
    return new _Decoration(from2, to, new NodeType2(attrs, spec));
  }
  /**
  The spec provided when creating this decoration. Can be useful
  if you've stored extra information in that object.
  */
  get spec() {
    return this.type.spec;
  }
  /**
  @internal
  */
  get inline() {
    return this.type instanceof InlineType;
  }
  /**
  @internal
  */
  get widget() {
    return this.type instanceof WidgetType;
  }
};
var none = [];
var noSpec = {};
var DecorationSet = class _DecorationSet {
  /**
  @internal
  */
  constructor(local, children) {
    this.local = local.length ? local : none;
    this.children = children.length ? children : none;
  }
  /**
  Create a set of decorations, using the structure of the given
  document. This will consume (modify) the `decorations` array, so
  you must make a copy if you want need to preserve that.
  */
  static create(doc3, decorations) {
    return decorations.length ? buildTree(decorations, doc3, 0, noSpec) : empty;
  }
  /**
  Find all decorations in this set which touch the given range
  (including decorations that start or end directly at the
  boundaries) and match the given predicate on their spec. When
  `start` and `end` are omitted, all decorations in the set are
  considered. When `predicate` isn't given, all decorations are
  assumed to match.
  */
  find(start, end, predicate) {
    let result = [];
    this.findInner(start == null ? 0 : start, end == null ? 1e9 : end, result, 0, predicate);
    return result;
  }
  findInner(start, end, result, offset, predicate) {
    for (let i2 = 0; i2 < this.local.length; i2++) {
      let span = this.local[i2];
      if (span.from <= end && span.to >= start && (!predicate || predicate(span.spec)))
        result.push(span.copy(span.from + offset, span.to + offset));
    }
    for (let i2 = 0; i2 < this.children.length; i2 += 3) {
      if (this.children[i2] < end && this.children[i2 + 1] > start) {
        let childOff = this.children[i2] + 1;
        this.children[i2 + 2].findInner(start - childOff, end - childOff, result, offset + childOff, predicate);
      }
    }
  }
  /**
  Map the set of decorations in response to a change in the
  document.
  */
  map(mapping, doc3, options) {
    if (this == empty || mapping.maps.length == 0)
      return this;
    return this.mapInner(mapping, doc3, 0, 0, options || noSpec);
  }
  /**
  @internal
  */
  mapInner(mapping, node2, offset, oldOffset, options) {
    let newLocal;
    if (this.local.length) {
      let cur = new FragmentCursor(node2.content);
      for (let i2 = 0; i2 < this.local.length; i2++) {
        let mapped = this.local[i2].map(mapping, offset, oldOffset);
        if (mapped && mapped.type.valid(node2, mapped, cur))
          (newLocal || (newLocal = [])).push(mapped);
        else if (options.onRemove)
          options.onRemove(this.local[i2].spec);
      }
    }
    if (this.children.length)
      return mapChildren(this.children, newLocal || [], mapping, node2, offset, oldOffset, options);
    else
      return newLocal ? new _DecorationSet(newLocal.sort(byPos), none) : empty;
  }
  /**
  Add the given array of decorations to the ones in the set,
  producing a new set. Consumes the `decorations` array. Needs
  access to the current document to create the appropriate tree
  structure.
  */
  add(doc3, decorations) {
    if (!decorations.length)
      return this;
    if (this == empty)
      return _DecorationSet.create(doc3, decorations);
    return this.addInner(doc3, decorations, 0);
  }
  addInner(doc3, decorations, offset) {
    let children, childIndex = 0;
    doc3.forEach((childNode, childOffset) => {
      let baseOffset = childOffset + offset, found2;
      if (!(found2 = takeSpansForNode(decorations, childNode, baseOffset)))
        return;
      if (!children)
        children = this.children.slice();
      while (childIndex < children.length && children[childIndex] < childOffset)
        childIndex += 3;
      if (children[childIndex] == childOffset)
        children[childIndex + 2] = children[childIndex + 2].addInner(childNode, found2, baseOffset + 1);
      else
        children.splice(childIndex, 0, childOffset, childOffset + childNode.nodeSize, buildTree(found2, childNode, baseOffset + 1, noSpec));
      childIndex += 3;
    });
    let local = moveSpans(childIndex ? withoutNulls(decorations) : decorations, -offset);
    if (local.length) {
      let cur = new FragmentCursor(doc3.content);
      for (let i2 = 0; i2 < local.length; i2++)
        if (!local[i2].type.valid(doc3, local[i2], cur))
          local.splice(i2--, 1);
    }
    return new _DecorationSet(local.length ? this.local.concat(local).sort(byPos) : this.local, children || this.children);
  }
  /**
  Create a new set that contains the decorations in this set, minus
  the ones in the given array.
  */
  remove(decorations) {
    if (decorations.length == 0 || this == empty)
      return this;
    return this.removeInner(decorations, 0);
  }
  removeInner(decorations, offset) {
    let children = this.children, local = this.local;
    for (let i2 = 0; i2 < children.length; i2 += 3) {
      let found2;
      let from2 = children[i2] + offset, to = children[i2 + 1] + offset;
      for (let j = 0, span; j < decorations.length; j++)
        if (span = decorations[j]) {
          if (span.from > from2 && span.to < to) {
            decorations[j] = null;
            (found2 || (found2 = [])).push(span);
          }
        }
      if (!found2)
        continue;
      if (children == this.children)
        children = this.children.slice();
      let removed = children[i2 + 2].removeInner(found2, from2 + 1);
      if (removed != empty) {
        children[i2 + 2] = removed;
      } else {
        children.splice(i2, 3);
        i2 -= 3;
      }
    }
    if (local.length) {
      for (let i2 = 0, span; i2 < decorations.length; i2++)
        if (span = decorations[i2]) {
          for (let j = 0; j < local.length; j++)
            if (local[j].eq(span, offset)) {
              if (local == this.local)
                local = this.local.slice();
              local.splice(j--, 1);
            }
        }
    }
    if (children == this.children && local == this.local)
      return this;
    return local.length || children.length ? new _DecorationSet(local, children) : empty;
  }
  forChild(offset, node2) {
    if (this == empty)
      return this;
    if (node2.isLeaf)
      return _DecorationSet.empty;
    let child, local;
    for (let i2 = 0; i2 < this.children.length; i2 += 3)
      if (this.children[i2] >= offset) {
        if (this.children[i2] == offset)
          child = this.children[i2 + 2];
        break;
      }
    let start = offset + 1, end = start + node2.content.size;
    for (let i2 = 0; i2 < this.local.length; i2++) {
      let dec = this.local[i2];
      if (dec.from < end && dec.to > start && dec.type instanceof InlineType) {
        let from2 = Math.max(start, dec.from) - start, to = Math.min(end, dec.to) - start;
        if (from2 < to)
          (local || (local = [])).push(dec.copy(from2, to));
      }
    }
    if (local) {
      let localSet = new _DecorationSet(local.sort(byPos), none);
      return child ? new DecorationGroup([localSet, child]) : localSet;
    }
    return child || empty;
  }
  /**
  @internal
  */
  eq(other) {
    if (this == other)
      return true;
    if (!(other instanceof _DecorationSet) || this.local.length != other.local.length || this.children.length != other.children.length)
      return false;
    for (let i2 = 0; i2 < this.local.length; i2++)
      if (!this.local[i2].eq(other.local[i2]))
        return false;
    for (let i2 = 0; i2 < this.children.length; i2 += 3)
      if (this.children[i2] != other.children[i2] || this.children[i2 + 1] != other.children[i2 + 1] || !this.children[i2 + 2].eq(other.children[i2 + 2]))
        return false;
    return true;
  }
  /**
  @internal
  */
  locals(node2) {
    return removeOverlap(this.localsInner(node2));
  }
  /**
  @internal
  */
  localsInner(node2) {
    if (this == empty)
      return none;
    if (node2.inlineContent || !this.local.some(InlineType.is))
      return this.local;
    let result = [];
    for (let i2 = 0; i2 < this.local.length; i2++) {
      if (!(this.local[i2].type instanceof InlineType))
        result.push(this.local[i2]);
    }
    return result;
  }
  forEachSet(f) {
    f(this);
  }
};
DecorationSet.empty = new DecorationSet([], []);
DecorationSet.removeOverlap = removeOverlap;
var empty = DecorationSet.empty;
var DecorationGroup = class _DecorationGroup {
  constructor(members) {
    this.members = members;
  }
  map(mapping, doc3) {
    const mappedDecos = this.members.map((member) => member.map(mapping, doc3, noSpec));
    return _DecorationGroup.from(mappedDecos);
  }
  forChild(offset, child) {
    if (child.isLeaf)
      return DecorationSet.empty;
    let found2 = [];
    for (let i2 = 0; i2 < this.members.length; i2++) {
      let result = this.members[i2].forChild(offset, child);
      if (result == empty)
        continue;
      if (result instanceof _DecorationGroup)
        found2 = found2.concat(result.members);
      else
        found2.push(result);
    }
    return _DecorationGroup.from(found2);
  }
  eq(other) {
    if (!(other instanceof _DecorationGroup) || other.members.length != this.members.length)
      return false;
    for (let i2 = 0; i2 < this.members.length; i2++)
      if (!this.members[i2].eq(other.members[i2]))
        return false;
    return true;
  }
  locals(node2) {
    let result, sorted = true;
    for (let i2 = 0; i2 < this.members.length; i2++) {
      let locals = this.members[i2].localsInner(node2);
      if (!locals.length)
        continue;
      if (!result) {
        result = locals;
      } else {
        if (sorted) {
          result = result.slice();
          sorted = false;
        }
        for (let j = 0; j < locals.length; j++)
          result.push(locals[j]);
      }
    }
    return result ? removeOverlap(sorted ? result : result.sort(byPos)) : none;
  }
  // Create a group for the given array of decoration sets, or return
  // a single set when possible.
  static from(members) {
    switch (members.length) {
      case 0:
        return empty;
      case 1:
        return members[0];
      default:
        return new _DecorationGroup(members.every((m) => m instanceof DecorationSet) ? members : members.reduce((r, m) => r.concat(m instanceof DecorationSet ? m : m.members), []));
    }
  }
  forEachSet(f) {
    for (let i2 = 0; i2 < this.members.length; i2++)
      this.members[i2].forEachSet(f);
  }
};
function mapChildren(oldChildren, newLocal, mapping, node2, offset, oldOffset, options) {
  let children = oldChildren.slice();
  for (let i2 = 0, baseOffset = oldOffset; i2 < mapping.maps.length; i2++) {
    let moved = 0;
    mapping.maps[i2].forEach((oldStart, oldEnd, newStart, newEnd) => {
      let dSize = newEnd - newStart - (oldEnd - oldStart);
      for (let i3 = 0; i3 < children.length; i3 += 3) {
        let end = children[i3 + 1];
        if (end < 0 || oldStart > end + baseOffset - moved)
          continue;
        let start = children[i3] + baseOffset - moved;
        if (oldEnd >= start) {
          children[i3 + 1] = oldStart <= start ? -2 : -1;
        } else if (oldStart >= baseOffset && dSize) {
          children[i3] += dSize;
          children[i3 + 1] += dSize;
        }
      }
      moved += dSize;
    });
    baseOffset = mapping.maps[i2].map(baseOffset, -1);
  }
  let mustRebuild = false;
  for (let i2 = 0; i2 < children.length; i2 += 3)
    if (children[i2 + 1] < 0) {
      if (children[i2 + 1] == -2) {
        mustRebuild = true;
        children[i2 + 1] = -1;
        continue;
      }
      let from2 = mapping.map(oldChildren[i2] + oldOffset), fromLocal = from2 - offset;
      if (fromLocal < 0 || fromLocal >= node2.content.size) {
        mustRebuild = true;
        continue;
      }
      let to = mapping.map(oldChildren[i2 + 1] + oldOffset, -1), toLocal = to - offset;
      let { index: index2, offset: childOffset } = node2.content.findIndex(fromLocal);
      let childNode = node2.maybeChild(index2);
      if (childNode && childOffset == fromLocal && childOffset + childNode.nodeSize == toLocal) {
        let mapped = children[i2 + 2].mapInner(mapping, childNode, from2 + 1, oldChildren[i2] + oldOffset + 1, options);
        if (mapped != empty) {
          children[i2] = fromLocal;
          children[i2 + 1] = toLocal;
          children[i2 + 2] = mapped;
        } else {
          children[i2 + 1] = -2;
          mustRebuild = true;
        }
      } else {
        mustRebuild = true;
      }
    }
  if (mustRebuild) {
    let decorations = mapAndGatherRemainingDecorations(children, oldChildren, newLocal, mapping, offset, oldOffset, options);
    let built = buildTree(decorations, node2, 0, options);
    newLocal = built.local;
    for (let i2 = 0; i2 < children.length; i2 += 3)
      if (children[i2 + 1] < 0) {
        children.splice(i2, 3);
        i2 -= 3;
      }
    for (let i2 = 0, j = 0; i2 < built.children.length; i2 += 3) {
      let from2 = built.children[i2];
      while (j < children.length && children[j] < from2)
        j += 3;
      children.splice(j, 0, built.children[i2], built.children[i2 + 1], built.children[i2 + 2]);
    }
  }
  return new DecorationSet(newLocal.sort(byPos), children);
}
function moveSpans(spans, offset) {
  if (!offset || !spans.length)
    return spans;
  let result = [];
  for (let i2 = 0; i2 < spans.length; i2++) {
    let span = spans[i2];
    result.push(new Decoration(span.from + offset, span.to + offset, span.type));
  }
  return result;
}
function mapAndGatherRemainingDecorations(children, oldChildren, decorations, mapping, offset, oldOffset, options) {
  function gather(set, oldOffset2) {
    for (let i2 = 0; i2 < set.local.length; i2++) {
      let mapped = set.local[i2].map(mapping, offset, oldOffset2);
      if (mapped)
        decorations.push(mapped);
      else if (options.onRemove)
        options.onRemove(set.local[i2].spec);
    }
    for (let i2 = 0; i2 < set.children.length; i2 += 3)
      gather(set.children[i2 + 2], set.children[i2] + oldOffset2 + 1);
  }
  for (let i2 = 0; i2 < children.length; i2 += 3)
    if (children[i2 + 1] == -1)
      gather(children[i2 + 2], oldChildren[i2] + oldOffset + 1);
  return decorations;
}
function takeSpansForNode(spans, node2, offset) {
  if (node2.isLeaf)
    return null;
  let end = offset + node2.nodeSize, found2 = null;
  for (let i2 = 0, span; i2 < spans.length; i2++) {
    if ((span = spans[i2]) && span.from > offset && span.to < end) {
      (found2 || (found2 = [])).push(span);
      spans[i2] = null;
    }
  }
  return found2;
}
function withoutNulls(array) {
  let result = [];
  for (let i2 = 0; i2 < array.length; i2++)
    if (array[i2] != null)
      result.push(array[i2]);
  return result;
}
function buildTree(spans, node2, offset, options) {
  let children = [], hasNulls = false;
  node2.forEach((childNode, localStart) => {
    let found2 = takeSpansForNode(spans, childNode, localStart + offset);
    if (found2) {
      hasNulls = true;
      let subtree = buildTree(found2, childNode, offset + localStart + 1, options);
      if (subtree != empty)
        children.push(localStart, localStart + childNode.nodeSize, subtree);
    }
  });
  let locals = moveSpans(hasNulls ? withoutNulls(spans) : spans, -offset).sort(byPos);
  if (locals.length) {
    let cur = new FragmentCursor(node2.content);
    for (let i2 = 0; i2 < locals.length; i2++)
      if (!locals[i2].type.valid(node2, locals[i2], cur)) {
        if (options.onRemove)
          options.onRemove(locals[i2].spec);
        locals.splice(i2--, 1);
      }
  }
  return locals.length || children.length ? new DecorationSet(locals, children) : empty;
}
function byPos(a, b) {
  return a.from - b.from || a.to - b.to;
}
function removeOverlap(spans) {
  let working = spans;
  for (let i2 = 0; i2 < working.length - 1; i2++) {
    let span = working[i2];
    if (span.from != span.to)
      for (let j = i2 + 1; j < working.length; j++) {
        let next = working[j];
        if (next.from == span.from) {
          if (next.to != span.to) {
            if (working == spans)
              working = spans.slice();
            working[j] = next.copy(next.from, span.to);
            insertAhead(working, j + 1, next.copy(span.to, next.to));
          }
          continue;
        } else {
          if (next.from < span.to) {
            if (working == spans)
              working = spans.slice();
            working[i2] = span.copy(span.from, next.from);
            insertAhead(working, j, span.copy(next.from, span.to));
          }
          break;
        }
      }
  }
  return working;
}
function insertAhead(array, i2, deco) {
  while (i2 < array.length && byPos(deco, array[i2]) > 0)
    i2++;
  array.splice(i2, 0, deco);
}
function viewDecorations(view) {
  let found2 = [];
  view.someProp("decorations", (f) => {
    let result = f(view.state);
    if (result && result != empty)
      found2.push(result);
  });
  if (view.cursorWrapper)
    found2.push(DecorationSet.create(view.state.doc, [view.cursorWrapper.deco]));
  return DecorationGroup.from(found2);
}
var observeOptions = {
  childList: true,
  characterData: true,
  characterDataOldValue: true,
  attributes: true,
  attributeOldValue: true,
  subtree: true
};
var useCharData = ie && ie_version <= 11;
var SelectionState = class {
  constructor() {
    this.anchorNode = null;
    this.anchorOffset = 0;
    this.focusNode = null;
    this.focusOffset = 0;
  }
  set(sel) {
    this.anchorNode = sel.anchorNode;
    this.anchorOffset = sel.anchorOffset;
    this.focusNode = sel.focusNode;
    this.focusOffset = sel.focusOffset;
  }
  clear() {
    this.anchorNode = this.focusNode = null;
  }
  eq(sel) {
    return sel.anchorNode == this.anchorNode && sel.anchorOffset == this.anchorOffset && sel.focusNode == this.focusNode && sel.focusOffset == this.focusOffset;
  }
};
var DOMObserver = class {
  constructor(view, handleDOMChange) {
    this.view = view;
    this.handleDOMChange = handleDOMChange;
    this.queue = [];
    this.flushingSoon = -1;
    this.observer = null;
    this.currentSelection = new SelectionState();
    this.onCharData = null;
    this.suppressingSelectionUpdates = false;
    this.lastChangedTextNode = null;
    this.observer = window.MutationObserver && new window.MutationObserver((mutations) => {
      for (let i2 = 0; i2 < mutations.length; i2++)
        this.queue.push(mutations[i2]);
      if (ie && ie_version <= 11 && mutations.some((m) => m.type == "childList" && m.removedNodes.length || m.type == "characterData" && m.oldValue.length > m.target.nodeValue.length)) {
        this.flushSoon();
      } else if (safari && view.composing && mutations.some((m) => m.type == "childList" && m.target.nodeName == "TR")) {
        view.input.badSafariComposition = true;
        this.flushSoon();
      } else {
        this.flush();
      }
    });
    if (useCharData) {
      this.onCharData = (e) => {
        this.queue.push({ target: e.target, type: "characterData", oldValue: e.prevValue });
        this.flushSoon();
      };
    }
    this.onSelectionChange = this.onSelectionChange.bind(this);
  }
  flushSoon() {
    if (this.flushingSoon < 0)
      this.flushingSoon = window.setTimeout(() => {
        this.flushingSoon = -1;
        this.flush();
      }, 20);
  }
  forceFlush() {
    if (this.flushingSoon > -1) {
      window.clearTimeout(this.flushingSoon);
      this.flushingSoon = -1;
      this.flush();
    }
  }
  start() {
    if (this.observer) {
      this.observer.takeRecords();
      this.observer.observe(this.view.dom, observeOptions);
    }
    if (this.onCharData)
      this.view.dom.addEventListener("DOMCharacterDataModified", this.onCharData);
    this.connectSelection();
  }
  stop() {
    if (this.observer) {
      let take = this.observer.takeRecords();
      if (take.length) {
        for (let i2 = 0; i2 < take.length; i2++)
          this.queue.push(take[i2]);
        window.setTimeout(() => this.flush(), 20);
      }
      this.observer.disconnect();
    }
    if (this.onCharData)
      this.view.dom.removeEventListener("DOMCharacterDataModified", this.onCharData);
    this.disconnectSelection();
  }
  connectSelection() {
    this.view.dom.ownerDocument.addEventListener("selectionchange", this.onSelectionChange);
  }
  disconnectSelection() {
    this.view.dom.ownerDocument.removeEventListener("selectionchange", this.onSelectionChange);
  }
  suppressSelectionUpdates() {
    this.suppressingSelectionUpdates = true;
    setTimeout(() => this.suppressingSelectionUpdates = false, 50);
  }
  onSelectionChange() {
    if (!hasFocusAndSelection(this.view))
      return;
    if (this.suppressingSelectionUpdates)
      return selectionToDOM(this.view);
    if (ie && ie_version <= 11 && !this.view.state.selection.empty) {
      let sel = this.view.domSelectionRange();
      if (sel.focusNode && isEquivalentPosition(sel.focusNode, sel.focusOffset, sel.anchorNode, sel.anchorOffset))
        return this.flushSoon();
    }
    this.flush();
  }
  setCurSelection() {
    this.currentSelection.set(this.view.domSelectionRange());
  }
  ignoreSelectionChange(sel) {
    if (!sel.focusNode)
      return true;
    let ancestors = /* @__PURE__ */ new Set(), container;
    for (let scan = sel.focusNode; scan; scan = parentNode(scan))
      ancestors.add(scan);
    for (let scan = sel.anchorNode; scan; scan = parentNode(scan))
      if (ancestors.has(scan)) {
        container = scan;
        break;
      }
    let desc = container && this.view.docView.nearestDesc(container);
    if (desc && desc.ignoreMutation({
      type: "selection",
      target: isText(container) ? container.parentNode : container
    })) {
      this.setCurSelection();
      return true;
    }
  }
  pendingRecords() {
    if (this.observer)
      for (let mut of this.observer.takeRecords())
        this.queue.push(mut);
    return this.queue;
  }
  flush() {
    let { view } = this;
    if (!view.docView || this.flushingSoon > -1)
      return;
    let mutations = this.pendingRecords();
    if (mutations.length)
      this.queue = [];
    let selRange, newSel = false;
    if (!this.suppressingSelectionUpdates && hasFocusAndSelection(view)) {
      selRange = view.domSelectionRange();
      newSel = !this.currentSelection.eq(selRange) && !this.ignoreSelectionChange(selRange);
    }
    let from2 = -1, to = -1, typeOver = false, added = [];
    if (view.editable) {
      for (let i2 = 0; i2 < mutations.length; i2++) {
        let result = this.registerMutation(mutations[i2], added);
        if (result) {
          from2 = from2 < 0 ? result.from : Math.min(result.from, from2);
          to = to < 0 ? result.to : Math.max(result.to, to);
          if (result.typeOver)
            typeOver = true;
        }
      }
    }
    if (added.some((n) => n.nodeName == "BR") && (view.input.lastKeyCode == 8 || view.input.lastKeyCode == 46 || chrome && (view.composing || view.input.compositionEndedAt > Date.now() - 50) && mutations.some((m) => m.type == "childList" && m.removedNodes.length))) {
      for (let node2 of added)
        if (node2.nodeName == "BR" && node2.parentNode) {
          let after = node2.nextSibling;
          while (after && isElt(after)) {
            if (after.contentEditable == "false") {
              node2.parentNode.removeChild(node2);
              break;
            }
            after = after.firstChild;
          }
        }
    } else if (gecko && added.length) {
      let brs = added.filter((n) => n.nodeName == "BR");
      if (brs.length == 2) {
        let [a, b] = brs;
        if (a.parentNode && a.parentNode.parentNode == b.parentNode)
          b.remove();
        else
          a.remove();
      } else {
        let { focusNode } = this.currentSelection;
        for (let br of brs) {
          let parent = br.parentNode;
          if (parent && parent.nodeName == "LI" && (!focusNode || blockParent(view, focusNode) != parent))
            br.remove();
        }
      }
    }
    let readSel = null;
    if (from2 < 0 && newSel && view.input.lastFocus > Date.now() - 200 && Math.max(view.input.lastTouch, view.input.lastClick.time) < Date.now() - 300 && selectionCollapsed(selRange) && (readSel = selectionFromDOM(view)) && readSel.eq(Selection.near(view.state.doc.resolve(0), 1))) {
      view.input.lastFocus = 0;
      selectionToDOM(view);
      this.currentSelection.set(selRange);
      view.scrollToSelection();
    } else if (from2 > -1 || newSel) {
      if (from2 > -1) {
        view.docView.markDirty(from2, to);
        checkCSS(view);
      }
      if (view.input.badSafariComposition) {
        view.input.badSafariComposition = false;
        fixUpBadSafariComposition(view, added);
      }
      this.handleDOMChange(from2, to, typeOver, added);
      if (view.docView && view.docView.dirty)
        view.updateState(view.state);
      else if (selRange && !this.currentSelection.eq(selRange))
        selectionToDOM(view);
      if (selRange)
        this.currentSelection.set(selRange);
    }
  }
  registerMutation(mut, added) {
    if (added.indexOf(mut.target) > -1)
      return null;
    let desc = this.view.docView.nearestDesc(mut.target);
    if (mut.type == "attributes" && (desc == this.view.docView || mut.attributeName == "contenteditable" || // Firefox sometimes fires spurious events for null/empty styles
    mut.attributeName == "style" && !mut.oldValue && !mut.target.getAttribute("style")))
      return null;
    if (!desc || desc.ignoreMutation(mut))
      return null;
    if (mut.type == "childList") {
      for (let i2 = 0; i2 < mut.addedNodes.length; i2++) {
        let node2 = mut.addedNodes[i2];
        added.push(node2);
        if (isText(node2))
          this.lastChangedTextNode = node2;
      }
      if (desc.contentDOM && desc.contentDOM != desc.dom && !desc.contentDOM.contains(mut.target))
        return { from: desc.posBefore, to: desc.posAfter };
      let prev = mut.previousSibling, next = mut.nextSibling;
      if (ie && ie_version <= 11 && mut.addedNodes.length) {
        for (let i2 = 0; i2 < mut.addedNodes.length; i2++) {
          let { previousSibling, nextSibling } = mut.addedNodes[i2];
          if (!previousSibling || Array.prototype.indexOf.call(mut.addedNodes, previousSibling) < 0)
            prev = previousSibling;
          if (!nextSibling || Array.prototype.indexOf.call(mut.addedNodes, nextSibling) < 0)
            next = nextSibling;
        }
      }
      let fromOffset = prev && prev.parentNode == mut.target ? domIndex(prev) + 1 : 0;
      let from2 = desc.localPosFromDOM(mut.target, fromOffset, -1);
      let toOffset = next && next.parentNode == mut.target ? domIndex(next) : mut.target.childNodes.length;
      let to = desc.localPosFromDOM(mut.target, toOffset, 1);
      return { from: from2, to };
    } else if (mut.type == "attributes") {
      return { from: desc.posAtStart - desc.border, to: desc.posAtEnd + desc.border };
    } else {
      this.lastChangedTextNode = mut.target;
      return {
        from: desc.posAtStart,
        to: desc.posAtEnd,
        // An event was generated for a text change that didn't change
        // any text. Mark the dom change to fall back to assuming the
        // selection was typed over with an identical value if it can't
        // find another change.
        typeOver: mut.target.nodeValue == mut.oldValue
      };
    }
  }
};
var cssChecked = /* @__PURE__ */ new WeakMap();
var cssCheckWarned = false;
function checkCSS(view) {
  if (cssChecked.has(view))
    return;
  cssChecked.set(view, null);
  if (["normal", "nowrap", "pre-line"].indexOf(getComputedStyle(view.dom).whiteSpace) !== -1) {
    view.requiresGeckoHackNode = gecko;
    if (cssCheckWarned)
      return;
    console["warn"]("ProseMirror expects the CSS white-space property to be set, preferably to 'pre-wrap'. It is recommended to load style/prosemirror.css from the prosemirror-view package.");
    cssCheckWarned = true;
  }
}
function rangeToSelectionRange(view, range) {
  let anchorNode = range.startContainer, anchorOffset = range.startOffset;
  let focusNode = range.endContainer, focusOffset = range.endOffset;
  let currentAnchor = view.domAtPos(view.state.selection.anchor);
  if (isEquivalentPosition(currentAnchor.node, currentAnchor.offset, focusNode, focusOffset))
    [anchorNode, anchorOffset, focusNode, focusOffset] = [focusNode, focusOffset, anchorNode, anchorOffset];
  return { anchorNode, anchorOffset, focusNode, focusOffset };
}
function safariShadowSelectionRange(view, selection) {
  if (selection.getComposedRanges) {
    let range = selection.getComposedRanges(view.root)[0];
    if (range)
      return rangeToSelectionRange(view, range);
  }
  let found2;
  function read(event) {
    event.preventDefault();
    event.stopImmediatePropagation();
    found2 = event.getTargetRanges()[0];
  }
  view.dom.addEventListener("beforeinput", read, true);
  document.execCommand("indent");
  view.dom.removeEventListener("beforeinput", read, true);
  return found2 ? rangeToSelectionRange(view, found2) : null;
}
function blockParent(view, node2) {
  for (let p = node2.parentNode; p && p != view.dom; p = p.parentNode) {
    let desc = view.docView.nearestDesc(p, true);
    if (desc && desc.node.isBlock)
      return p;
  }
  return null;
}
function fixUpBadSafariComposition(view, addedNodes) {
  var _a;
  let { focusNode, focusOffset } = view.domSelectionRange();
  for (let node2 of addedNodes) {
    if (((_a = node2.parentNode) === null || _a === void 0 ? void 0 : _a.nodeName) == "TR") {
      let nextCell = node2.nextSibling;
      while (nextCell && (nextCell.nodeName != "TD" && nextCell.nodeName != "TH"))
        nextCell = nextCell.nextSibling;
      if (nextCell) {
        let parent = nextCell;
        for (; ; ) {
          let first = parent.firstChild;
          if (!first || !isElt(first) || first.contentEditable == "false" || /^(BR|IMG)$/.test(first.nodeName))
            break;
          parent = first;
        }
        parent.insertBefore(node2, parent.firstChild);
        if (focusNode == node2)
          view.domSelection().collapse(node2, focusOffset);
      } else {
        node2.parentNode.removeChild(node2);
      }
    }
  }
}
function parseBetween(view, from_, to_, addedNodes) {
  let { node: parent, fromOffset, toOffset, from: from2, to } = view.docView.parseRange(from_, to_);
  let domSel = view.domSelectionRange();
  let find;
  let anchor = domSel.anchorNode;
  if (anchor && contains(view.dom, anchor)) {
    find = [{ node: anchor, offset: domSel.anchorOffset }];
    if (!selectionCollapsed(domSel))
      find.push({ node: domSel.focusNode, offset: domSel.focusOffset });
  }
  if (chrome && view.input.lastKeyCode === 8) {
    for (let off = toOffset; off > fromOffset; off--) {
      let node2 = parent.childNodes[off - 1], desc = node2.pmViewDesc;
      if (node2.nodeName == "BR" && !desc) {
        toOffset = off;
        break;
      }
      if (!desc || desc.size)
        break;
    }
  }
  let startDoc = view.state.doc;
  let parser = view.someProp("domParser") || DOMParser.fromSchema(view.state.schema);
  let $from = startDoc.resolve(from2);
  let sel = null, doc3 = parser.parse(parent, {
    topNode: $from.parent,
    topMatch: $from.parent.contentMatchAt($from.index()),
    topOpen: true,
    from: fromOffset,
    to: toOffset,
    preserveWhitespace: $from.parent.type.whitespace == "pre" ? "full" : true,
    findPositions: find,
    ruleFromNode: ruleFromNode(addedNodes),
    context: $from
  });
  if (find && find[0].pos != null) {
    let anchor2 = find[0].pos, head = find[1] && find[1].pos;
    if (head == null)
      head = anchor2;
    sel = { anchor: anchor2 + from2, head: head + from2 };
  }
  return { doc: doc3, sel, from: from2, to };
}
var ruleFromNode = (added) => (dom) => {
  let desc = dom.pmViewDesc;
  if (desc) {
    return desc.parseRule(added);
  } else if (dom.nodeName == "BR" && dom.parentNode) {
    if (safari && /^(ul|ol)$/i.test(dom.parentNode.nodeName)) {
      let skip = document.createElement("div");
      skip.appendChild(document.createElement("li"));
      return { skip };
    } else if (dom.parentNode.lastChild == dom || safari && /^(tr|table)$/i.test(dom.parentNode.nodeName)) {
      return { ignore: true };
    }
  } else if (dom.nodeName == "IMG" && dom.getAttribute("mark-placeholder")) {
    return { ignore: true };
  }
  return null;
};
var isInline = /^(a|abbr|acronym|b|bd[io]|big|br|button|cite|code|data(list)?|del|dfn|em|i|img|ins|kbd|label|map|mark|meter|output|q|ruby|s|samp|small|span|strong|su[bp]|time|u|tt|var)$/i;
function readDOMChange(view, from2, to, typeOver, addedNodes) {
  let compositionID = view.input.compositionPendingChanges || (view.composing ? view.input.compositionID : 0);
  view.input.compositionPendingChanges = 0;
  if (from2 < 0) {
    let origin = view.input.lastSelectionTime > Date.now() - 50 ? view.input.lastSelectionOrigin : null;
    let newSel = selectionFromDOM(view, origin);
    if (newSel && !view.state.selection.eq(newSel)) {
      if (chrome && android && view.input.lastKeyCode === 13 && Date.now() - 100 < view.input.lastKeyCodeTime && view.someProp("handleKeyDown", (f) => f(view, keyEvent(13, "Enter"))))
        return;
      let tr = view.state.tr.setSelection(newSel);
      if (origin == "pointer")
        tr.setMeta("pointer", true);
      else if (origin == "key")
        tr.scrollIntoView();
      if (compositionID)
        tr.setMeta("composition", compositionID);
      view.dispatch(tr);
    }
    return;
  }
  let $before = view.state.doc.resolve(from2);
  let shared = $before.sharedDepth(to);
  from2 = $before.before(shared + 1);
  to = view.state.doc.resolve(to).after(shared + 1);
  let sel = view.state.selection;
  let parse2 = parseBetween(view, from2, to, addedNodes);
  let doc3 = view.state.doc, compare = doc3.slice(parse2.from, parse2.to);
  let preferredPos, preferredSide;
  if (view.input.lastKeyCode === 8 && Date.now() - 100 < view.input.lastKeyCodeTime) {
    preferredPos = view.state.selection.to;
    preferredSide = "end";
  } else {
    preferredPos = view.state.selection.from;
    preferredSide = "start";
  }
  view.input.lastKeyCode = null;
  let change = findDiff(compare.content, parse2.doc.content, parse2.from, preferredPos, preferredSide);
  if (change)
    view.input.domChangeCount++;
  if ((ios && view.input.lastIOSEnter > Date.now() - 225 || android) && addedNodes.some((n) => isElt(n) && !isInline.test(n.nodeName)) && (!change || change.endA >= change.endB) && view.someProp("handleKeyDown", (f) => f(view, keyEvent(13, "Enter")))) {
    view.input.lastIOSEnter = 0;
    return;
  }
  if (!change) {
    if (typeOver && sel instanceof TextSelection && !sel.empty && sel.$head.sameParent(sel.$anchor) && !view.composing && !(parse2.sel && parse2.sel.anchor != parse2.sel.head)) {
      change = { start: sel.from, endA: sel.to, endB: sel.to };
    } else {
      if (parse2.sel) {
        let sel2 = resolveSelection(view, view.state.doc, parse2.sel);
        if (sel2 && !sel2.eq(view.state.selection)) {
          let tr = view.state.tr.setSelection(sel2);
          if (compositionID)
            tr.setMeta("composition", compositionID);
          view.dispatch(tr);
        }
      }
      return;
    }
  }
  if (view.state.selection.from < view.state.selection.to && change.start == change.endB && view.state.selection instanceof TextSelection) {
    if (change.start > view.state.selection.from && change.start <= view.state.selection.from + 2 && view.state.selection.from >= parse2.from) {
      change.start = view.state.selection.from;
    } else if (change.endA < view.state.selection.to && change.endA >= view.state.selection.to - 2 && view.state.selection.to <= parse2.to) {
      change.endB += view.state.selection.to - change.endA;
      change.endA = view.state.selection.to;
    }
  }
  if (ie && ie_version <= 11 && change.endB == change.start + 1 && change.endA == change.start && change.start > parse2.from && parse2.doc.textBetween(change.start - parse2.from - 1, change.start - parse2.from + 1) == "  ") {
    change.start--;
    change.endA--;
    change.endB--;
  }
  let $from = parse2.doc.resolveNoCache(change.start - parse2.from);
  let $to = parse2.doc.resolveNoCache(change.endB - parse2.from);
  let $fromA = doc3.resolve(change.start);
  let inlineChange = $from.sameParent($to) && $from.parent.inlineContent && $fromA.end() >= change.endA;
  if ((ios && view.input.lastIOSEnter > Date.now() - 225 && (!inlineChange || addedNodes.some((n) => n.nodeName == "DIV" || n.nodeName == "P")) || !inlineChange && looksLikeEnter(parse2.doc, $from.pos, $to.pos)) && view.someProp("handleKeyDown", (f) => f(view, keyEvent(13, "Enter")))) {
    view.input.lastIOSEnter = 0;
    return;
  }
  if (view.state.selection.anchor > change.start && (inlineChange ? change.endA > change.start && change.endB == change.start : looksLikeBlockJoin(doc3, change.start, change.endA, $from, $to)) && view.someProp("handleKeyDown", (f) => f(view, keyEvent(8, "Backspace")))) {
    if (android && chrome)
      view.domObserver.suppressSelectionUpdates();
    return;
  }
  if (chrome && change.endB == change.start)
    view.input.lastChromeDelete = Date.now();
  if (android && !inlineChange && $from.start() != $to.start() && $to.parentOffset == 0 && $from.depth == $to.depth && parse2.sel && parse2.sel.anchor == parse2.sel.head && parse2.sel.head == change.endA) {
    change.endB -= 2;
    $to = parse2.doc.resolveNoCache(change.endB - parse2.from);
    setTimeout(() => {
      view.someProp("handleKeyDown", function(f) {
        return f(view, keyEvent(13, "Enter"));
      });
    }, 20);
  }
  let chFrom = change.start, chTo = change.endA;
  let mkTr = (base2) => {
    let tr = base2 || view.state.tr.replace(chFrom, chTo, parse2.doc.slice(change.start - parse2.from, change.endB - parse2.from));
    if (parse2.sel) {
      let sel2 = resolveSelection(view, tr.doc, parse2.sel);
      if (sel2 && !(chrome && view.composing && sel2.empty && (change.start != change.endB || view.input.lastChromeDelete < Date.now() - 100) && (sel2.head == chFrom || sel2.head == tr.mapping.map(chTo) - 1) || ie && sel2.empty && sel2.head == chFrom))
        tr.setSelection(sel2);
    }
    if (compositionID)
      tr.setMeta("composition", compositionID);
    return tr.scrollIntoView();
  };
  let markChange;
  if (inlineChange) {
    if ($from.pos == $to.pos) {
      if (ie && ie_version <= 11 && $from.parentOffset == 0) {
        view.domObserver.suppressSelectionUpdates();
        setTimeout(() => selectionToDOM(view), 20);
      }
      let tr = mkTr(view.state.tr.delete(chFrom, chTo));
      let marks = doc3.resolve(change.start).marksAcross(doc3.resolve(change.endA));
      if (marks)
        tr.ensureMarks(marks);
      view.dispatch(tr);
    } else if (
      // Adding or removing a mark
      change.endA == change.endB && (markChange = isMarkChange($from.parent.content.cut($from.parentOffset, $to.parentOffset), $fromA.parent.content.cut($fromA.parentOffset, change.endA - $fromA.start())))
    ) {
      let tr = mkTr(view.state.tr);
      if (markChange.type == "add")
        tr.addMark(chFrom, chTo, markChange.mark);
      else
        tr.removeMark(chFrom, chTo, markChange.mark);
      view.dispatch(tr);
    } else if ($from.parent.child($from.index()).isText && $from.index() == $to.index() - ($to.textOffset ? 0 : 1)) {
      let text4 = $from.parent.textBetween($from.parentOffset, $to.parentOffset);
      let deflt = () => mkTr(view.state.tr.insertText(text4, chFrom, chTo));
      if (!view.someProp("handleTextInput", (f) => f(view, chFrom, chTo, text4, deflt)))
        view.dispatch(deflt());
    } else {
      view.dispatch(mkTr());
    }
  } else {
    view.dispatch(mkTr());
  }
}
function resolveSelection(view, doc3, parsedSel) {
  if (Math.max(parsedSel.anchor, parsedSel.head) > doc3.content.size)
    return null;
  return selectionBetween(view, doc3.resolve(parsedSel.anchor), doc3.resolve(parsedSel.head));
}
function isMarkChange(cur, prev) {
  let curMarks = cur.firstChild.marks, prevMarks = prev.firstChild.marks;
  let added = curMarks, removed = prevMarks, type, mark, update;
  for (let i2 = 0; i2 < prevMarks.length; i2++)
    added = prevMarks[i2].removeFromSet(added);
  for (let i2 = 0; i2 < curMarks.length; i2++)
    removed = curMarks[i2].removeFromSet(removed);
  if (added.length == 1 && removed.length == 0) {
    mark = added[0];
    type = "add";
    update = (node2) => node2.mark(mark.addToSet(node2.marks));
  } else if (added.length == 0 && removed.length == 1) {
    mark = removed[0];
    type = "remove";
    update = (node2) => node2.mark(mark.removeFromSet(node2.marks));
  } else {
    return null;
  }
  let updated = [];
  for (let i2 = 0; i2 < prev.childCount; i2++)
    updated.push(update(prev.child(i2)));
  if (Fragment.from(updated).eq(cur))
    return { mark, type };
}
function looksLikeBlockJoin(old, start, end, $newStart, $newEnd) {
  if (
    // The content must have shrunk
    end - start <= $newEnd.pos - $newStart.pos || // newEnd must point directly at or after the end of the block that newStart points into
    skipClosingAndOpening($newStart, true, false) < $newEnd.pos
  )
    return false;
  let $start = old.resolve(start);
  if (!$newStart.parent.inlineContent) {
    let after = $start.nodeAfter;
    return after != null && end == start + after.nodeSize;
  }
  if ($start.parentOffset < $start.parent.content.size || !$start.parent.isTextblock)
    return false;
  let $next = old.resolve(skipClosingAndOpening($start, true, true));
  if (!$next.parent.isTextblock || $next.pos > end || skipClosingAndOpening($next, true, false) < end)
    return false;
  return $newStart.parent.content.cut($newStart.parentOffset).eq($next.parent.content);
}
function looksLikeEnter(content3, from2, to) {
  let newTextlines = 0, newLeaves = 0;
  content3.nodesBetween(from2, to, (node2, pos) => {
    if (node2.isTextblock && pos >= from2 && pos < to)
      newTextlines++;
    else if (node2.isText ? /\S/.test(node2.text.slice(Math.max(0, from2 - pos), Math.min(node2.nodeSize, to - pos))) : node2.isLeaf)
      newLeaves++;
  });
  return newLeaves == 0 && newTextlines == 1;
}
function skipClosingAndOpening($pos, fromEnd, mayOpen) {
  let depth = $pos.depth, end = fromEnd ? $pos.end() : $pos.pos;
  while (depth > 0 && (fromEnd || $pos.indexAfter(depth) == $pos.node(depth).childCount)) {
    depth--;
    end++;
    fromEnd = false;
  }
  if (mayOpen) {
    let next = $pos.node(depth).maybeChild($pos.indexAfter(depth));
    while (next && !next.isLeaf) {
      next = next.firstChild;
      end++;
    }
  }
  return end;
}
function findDiff(a, b, pos, preferredPos, preferredSide) {
  let start = a.findDiffStart(b, pos), lenA = pos + a.size, lenB = pos + b.size;
  if (start == null)
    return null;
  let { a: endA, b: endB } = a.findDiffEnd(b, lenA, lenB);
  if (preferredSide == "end") {
    let adjust = Math.max(0, start - Math.min(endA, endB));
    preferredPos -= endA + adjust - start;
  }
  if (endA < start && lenA < lenB) {
    let move = preferredPos <= start && preferredPos >= endA ? start - preferredPos : 0;
    start -= move;
    endB = start + (endB - endA);
    endA = start;
  } else if (endB < start) {
    let move = preferredPos <= start && preferredPos >= endB ? start - preferredPos : 0;
    start -= move;
    endA = start + (endA - endB);
    endB = start;
  }
  return { start, endA, endB };
}
var EditorView = class {
  /**
  Create a view. `place` may be a DOM node that the editor should
  be appended to, a function that will place it into the document,
  or an object whose `mount` property holds the node to use as the
  document container. If it is `null`, the editor will not be
  added to the document.
  */
  constructor(place, props) {
    this._root = null;
    this.focused = false;
    this.trackWrites = null;
    this.mounted = false;
    this.markCursor = null;
    this.cursorWrapper = null;
    this.lastSelectedViewDesc = void 0;
    this.input = new InputState();
    this.prevDirectPlugins = [];
    this.pluginViews = [];
    this.requiresGeckoHackNode = false;
    this.dragging = null;
    this._props = props;
    this.state = props.state;
    this.directPlugins = props.plugins || [];
    this.directPlugins.forEach(checkStateComponent);
    this.dispatch = this.dispatch.bind(this);
    this.dom = place && place.mount || document.createElement("div");
    if (place) {
      if (place.appendChild)
        place.appendChild(this.dom);
      else if (typeof place == "function")
        place(this.dom);
      else if (place.mount)
        this.mounted = true;
    }
    this.editable = getEditable(this);
    updateCursorWrapper(this);
    this.nodeViews = buildNodeViews(this);
    this.docView = docViewDesc(this.state.doc, computeDocDeco(this), viewDecorations(this), this.dom, this);
    this.domObserver = new DOMObserver(this, (from2, to, typeOver, added) => readDOMChange(this, from2, to, typeOver, added));
    this.domObserver.start();
    initInput(this);
    this.updatePluginViews();
  }
  /**
  Holds `true` when a
  [composition](https://w3c.github.io/uievents/#events-compositionevents)
  is active.
  */
  get composing() {
    return this.input.composing;
  }
  /**
  The view's current [props](https://prosemirror.net/docs/ref/#view.EditorProps).
  */
  get props() {
    if (this._props.state != this.state) {
      let prev = this._props;
      this._props = {};
      for (let name in prev)
        this._props[name] = prev[name];
      this._props.state = this.state;
    }
    return this._props;
  }
  /**
  Update the view's props. Will immediately cause an update to
  the DOM.
  */
  update(props) {
    if (props.handleDOMEvents != this._props.handleDOMEvents)
      ensureListeners(this);
    let prevProps = this._props;
    this._props = props;
    if (props.plugins) {
      props.plugins.forEach(checkStateComponent);
      this.directPlugins = props.plugins;
    }
    this.updateStateInner(props.state, prevProps);
  }
  /**
  Update the view by updating existing props object with the object
  given as argument. Equivalent to `view.update(Object.assign({},
  view.props, props))`.
  */
  setProps(props) {
    let updated = {};
    for (let name in this._props)
      updated[name] = this._props[name];
    updated.state = this.state;
    for (let name in props)
      updated[name] = props[name];
    this.update(updated);
  }
  /**
  Update the editor's `state` prop, without touching any of the
  other props.
  */
  updateState(state) {
    this.updateStateInner(state, this._props);
  }
  updateStateInner(state, prevProps) {
    var _a;
    let prev = this.state, redraw = false, updateSel = false;
    if (state.storedMarks && this.composing) {
      clearComposition(this);
      updateSel = true;
    }
    this.state = state;
    let pluginsChanged = prev.plugins != state.plugins || this._props.plugins != prevProps.plugins;
    if (pluginsChanged || this._props.plugins != prevProps.plugins || this._props.nodeViews != prevProps.nodeViews) {
      let nodeViews = buildNodeViews(this);
      if (changedNodeViews(nodeViews, this.nodeViews)) {
        this.nodeViews = nodeViews;
        redraw = true;
      }
    }
    if (pluginsChanged || prevProps.handleDOMEvents != this._props.handleDOMEvents) {
      ensureListeners(this);
    }
    this.editable = getEditable(this);
    updateCursorWrapper(this);
    let innerDeco = viewDecorations(this), outerDeco = computeDocDeco(this);
    let scroll = prev.plugins != state.plugins && !prev.doc.eq(state.doc) ? "reset" : state.scrollToSelection > prev.scrollToSelection ? "to selection" : "preserve";
    let updateDoc = redraw || !this.docView.matchesNode(state.doc, outerDeco, innerDeco);
    if (updateDoc || !state.selection.eq(prev.selection))
      updateSel = true;
    let oldScrollPos = scroll == "preserve" && updateSel && this.dom.style.overflowAnchor == null && storeScrollPos(this);
    if (updateSel) {
      this.domObserver.stop();
      let forceSelUpdate = updateDoc && (ie || chrome) && !this.composing && !prev.selection.empty && !state.selection.empty && selectionContextChanged(prev.selection, state.selection);
      if (updateDoc) {
        let chromeKludge = chrome ? this.trackWrites = this.domSelectionRange().focusNode : null;
        if (this.composing)
          this.input.compositionNode = findCompositionNode(this);
        if (redraw || !this.docView.update(state.doc, outerDeco, innerDeco, this)) {
          this.docView.updateOuterDeco(outerDeco);
          this.docView.destroy();
          this.docView = docViewDesc(state.doc, outerDeco, innerDeco, this.dom, this);
        }
        if (chromeKludge && (!this.trackWrites || !this.dom.contains(this.trackWrites)))
          forceSelUpdate = true;
      }
      let mouseDown = this.input.mouseDown;
      if (forceSelUpdate || !(mouseDown && this.domObserver.currentSelection.eq(this.domSelectionRange()) && anchorInRightPlace(this) && mouseDown.delaySelUpdate())) {
        selectionToDOM(this, forceSelUpdate);
      } else {
        syncNodeSelection(this, state.selection);
        this.domObserver.setCurSelection();
      }
      this.domObserver.start();
    }
    this.updatePluginViews(prev);
    if (((_a = this.dragging) === null || _a === void 0 ? void 0 : _a.node) && !prev.doc.eq(state.doc))
      this.updateDraggedNode(this.dragging, prev);
    if (scroll == "reset") {
      this.dom.scrollTop = 0;
    } else if (scroll == "to selection") {
      this.scrollToSelection();
    } else if (oldScrollPos) {
      resetScrollPos(oldScrollPos);
    }
  }
  /**
  @internal
  */
  scrollToSelection() {
    let startDOM = this.domSelectionRange().focusNode;
    if (!startDOM || !contains(this.dom, startDOM)) ;
    else if (this.someProp("handleScrollToSelection", (f) => f(this))) ;
    else if (this.state.selection instanceof NodeSelection) {
      let target = this.docView.domAfterPos(this.state.selection.from);
      if (isElt(target))
        scrollRectIntoView(this, target.getBoundingClientRect(), startDOM);
    } else {
      scrollRectIntoView(this, this.coordsAtPos(this.state.selection.head, 1), startDOM);
    }
  }
  destroyPluginViews() {
    let view;
    while (view = this.pluginViews.pop())
      if (view.destroy)
        view.destroy();
  }
  updatePluginViews(prevState) {
    if (!prevState || prevState.plugins != this.state.plugins || this.directPlugins != this.prevDirectPlugins) {
      this.prevDirectPlugins = this.directPlugins;
      this.destroyPluginViews();
      for (let i2 = 0; i2 < this.directPlugins.length; i2++) {
        let plugin = this.directPlugins[i2];
        if (plugin.spec.view)
          this.pluginViews.push(plugin.spec.view(this));
      }
      for (let i2 = 0; i2 < this.state.plugins.length; i2++) {
        let plugin = this.state.plugins[i2];
        if (plugin.spec.view)
          this.pluginViews.push(plugin.spec.view(this));
      }
    } else {
      for (let i2 = 0; i2 < this.pluginViews.length; i2++) {
        let pluginView = this.pluginViews[i2];
        if (pluginView.update)
          pluginView.update(this, prevState);
      }
    }
  }
  updateDraggedNode(dragging, prev) {
    let sel = dragging.node, found2 = -1;
    if (sel.from < this.state.doc.content.size && this.state.doc.nodeAt(sel.from) == sel.node) {
      found2 = sel.from;
    } else {
      let movedPos = sel.from + (this.state.doc.content.size - prev.doc.content.size);
      let moved = movedPos > 0 && movedPos < this.state.doc.content.size && this.state.doc.nodeAt(movedPos);
      if (moved == sel.node)
        found2 = movedPos;
    }
    this.dragging = new Dragging(dragging.slice, dragging.move, found2 < 0 ? void 0 : NodeSelection.create(this.state.doc, found2));
  }
  someProp(propName, f) {
    let prop = this._props && this._props[propName], value;
    if (prop != null && (value = f ? f(prop) : prop))
      return value;
    for (let i2 = 0; i2 < this.directPlugins.length; i2++) {
      let prop2 = this.directPlugins[i2].props[propName];
      if (prop2 != null && (value = f ? f(prop2) : prop2))
        return value;
    }
    let plugins = this.state.plugins;
    if (plugins)
      for (let i2 = 0; i2 < plugins.length; i2++) {
        let prop2 = plugins[i2].props[propName];
        if (prop2 != null && (value = f ? f(prop2) : prop2))
          return value;
      }
  }
  /**
  Query whether the view has focus.
  */
  hasFocus() {
    if (ie) {
      let node2 = this.root.activeElement;
      if (node2 == this.dom)
        return true;
      if (!node2 || !this.dom.contains(node2))
        return false;
      while (node2 && this.dom != node2 && this.dom.contains(node2)) {
        if (node2.contentEditable == "false")
          return false;
        node2 = node2.parentElement;
      }
      return true;
    }
    return this.root.activeElement == this.dom;
  }
  /**
  Focus the editor.
  */
  focus() {
    this.domObserver.stop();
    if (this.editable)
      focusPreventScroll(this.dom);
    selectionToDOM(this);
    this.domObserver.start();
  }
  /**
  Get the document root in which the editor exists. This will
  usually be the top-level `document`, but might be a [shadow
  DOM](https://developer.mozilla.org/en-US/docs/Web/Web_Components/Shadow_DOM)
  root if the editor is inside one.
  */
  get root() {
    let cached = this._root;
    if (cached == null)
      for (let search2 = this.dom.parentNode; search2; search2 = search2.parentNode) {
        if (search2.nodeType == 9 || search2.nodeType == 11 && search2.host) {
          if (!search2.getSelection)
            Object.getPrototypeOf(search2).getSelection = () => search2.ownerDocument.getSelection();
          return this._root = search2;
        }
      }
    return cached || document;
  }
  /**
  When an existing editor view is moved to a new document or
  shadow tree, call this to make it recompute its root.
  */
  updateRoot() {
    this._root = null;
  }
  /**
  Given a pair of viewport coordinates, return the document
  position that corresponds to them. May return null if the given
  coordinates aren't inside of the editor. When an object is
  returned, its `pos` property is the position nearest to the
  coordinates, and its `inside` property holds the position of the
  inner node that the position falls inside of, or -1 if it is at
  the top level, not in any node.
  */
  posAtCoords(coords) {
    return posAtCoords(this, coords);
  }
  /**
  Returns the viewport rectangle at a given document position.
  `left` and `right` will be the same number, as this returns a
  flat cursor-ish rectangle. If the position is between two things
  that aren't directly adjacent, `side` determines which element
  is used. When < 0, the element before the position is used,
  otherwise the element after.
  */
  coordsAtPos(pos, side = 1) {
    return coordsAtPos(this, pos, side);
  }
  /**
  Find the DOM position that corresponds to the given document
  position. When `side` is negative, find the position as close as
  possible to the content before the position. When positive,
  prefer positions close to the content after the position. When
  zero, prefer as shallow a position as possible.
  
  Note that you should **not** mutate the editor's internal DOM,
  only inspect it (and even that is usually not necessary).
  */
  domAtPos(pos, side = 0) {
    return this.docView.domFromPos(pos, side);
  }
  /**
  Find the DOM node that represents the document node after the
  given position. May return `null` when the position doesn't point
  in front of a node or if the node is inside an opaque node view.
  
  This is intended to be able to call things like
  `getBoundingClientRect` on that DOM node. Do **not** mutate the
  editor DOM directly, or add styling this way, since that will be
  immediately overriden by the editor as it redraws the node.
  */
  nodeDOM(pos) {
    let desc = this.docView.descAt(pos);
    return desc ? desc.nodeDOM : null;
  }
  /**
  Find the document position that corresponds to a given DOM
  position. (Whenever possible, it is preferable to inspect the
  document structure directly, rather than poking around in the
  DOM, but sometimes—for example when interpreting an event
  target—you don't have a choice.)
  
  The `bias` parameter can be used to influence which side of a DOM
  node to use when the position is inside a leaf node.
  */
  posAtDOM(node2, offset, bias = -1) {
    let pos = this.docView.posFromDOM(node2, offset, bias);
    if (pos == null)
      throw new RangeError("DOM position not inside the editor");
    return pos;
  }
  /**
  Find out whether the selection is at the end of a textblock when
  moving in a given direction. When, for example, given `"left"`,
  it will return true if moving left from the current cursor
  position would leave that position's parent textblock. Will apply
  to the view's current state by default, but it is possible to
  pass a different state.
  */
  endOfTextblock(dir, state) {
    return endOfTextblock(this, state || this.state, dir);
  }
  /**
  Run the editor's paste logic with the given HTML string. The
  `event`, if given, will be passed to the
  [`handlePaste`](https://prosemirror.net/docs/ref/#view.EditorProps.handlePaste) hook.
  */
  pasteHTML(html2, event) {
    return doPaste(this, "", html2, false, event || new ClipboardEvent("paste"));
  }
  /**
  Run the editor's paste logic with the given plain-text input.
  */
  pasteText(text4, event) {
    return doPaste(this, text4, null, true, event || new ClipboardEvent("paste"));
  }
  /**
  Serialize the given slice as it would be if it was copied from
  this editor. Returns a DOM element that contains a
  representation of the slice as its children, a textual
  representation, and the transformed slice (which can be
  different from the given input due to hooks like
  [`transformCopied`](https://prosemirror.net/docs/ref/#view.EditorProps.transformCopied)).
  */
  serializeForClipboard(slice2) {
    return serializeForClipboard(this, slice2);
  }
  /**
  Removes the editor from the DOM and destroys all [node
  views](https://prosemirror.net/docs/ref/#view.NodeView).
  */
  destroy() {
    if (!this.docView)
      return;
    destroyInput(this);
    this.destroyPluginViews();
    if (this.mounted) {
      this.docView.update(this.state.doc, [], viewDecorations(this), this);
      this.dom.textContent = "";
    } else if (this.dom.parentNode) {
      this.dom.parentNode.removeChild(this.dom);
    }
    this.docView.destroy();
    this.docView = null;
    clearReusedRange();
  }
  /**
  This is true when the view has been
  [destroyed](https://prosemirror.net/docs/ref/#view.EditorView.destroy) (and thus should not be
  used anymore).
  */
  get isDestroyed() {
    return this.docView == null;
  }
  /**
  Used for testing.
  */
  dispatchEvent(event) {
    return dispatchEvent(this, event);
  }
  /**
  @internal
  */
  domSelectionRange() {
    let sel = this.dom.isConnected !== false && this.domSelection();
    if (!sel)
      return { focusNode: null, focusOffset: 0, anchorNode: null, anchorOffset: 0 };
    return safari && this.root.nodeType === 11 && deepActiveElement(this.dom.ownerDocument) == this.dom && safariShadowSelectionRange(this, sel) || sel;
  }
  /**
  @internal
  */
  domSelection() {
    return this.root.getSelection();
  }
};
EditorView.prototype.dispatch = function(tr) {
  let dispatchTransaction = this._props.dispatchTransaction;
  if (dispatchTransaction)
    dispatchTransaction.call(this, tr);
  else
    this.updateState(this.state.apply(tr));
};
function computeDocDeco(view) {
  let attrs = /* @__PURE__ */ Object.create(null);
  attrs.class = "ProseMirror";
  attrs.contenteditable = String(view.editable);
  view.someProp("attributes", (value) => {
    if (typeof value == "function")
      value = value(view.state);
    if (value)
      for (let attr in value) {
        if (attr == "class")
          attrs.class += " " + value[attr];
        else if (attr == "style")
          attrs.style = (attrs.style ? attrs.style + ";" : "") + value[attr];
        else if (!attrs[attr] && attr != "contenteditable" && attr != "nodeName")
          attrs[attr] = String(value[attr]);
      }
  });
  if (!attrs.translate)
    attrs.translate = "no";
  return [Decoration.node(0, view.state.doc.content.size, attrs)];
}
function updateCursorWrapper(view) {
  if (view.markCursor) {
    let dom = document.createElement("img");
    dom.className = "ProseMirror-separator";
    dom.setAttribute("mark-placeholder", "true");
    dom.setAttribute("alt", "");
    view.cursorWrapper = { dom, deco: Decoration.widget(view.state.selection.from, dom, { raw: true, marks: view.markCursor }) };
  } else {
    view.cursorWrapper = null;
  }
}
function getEditable(view) {
  return !view.someProp("editable", (value) => value(view.state) === false);
}
function selectionContextChanged(sel1, sel2) {
  let depth = Math.min(sel1.$anchor.sharedDepth(sel1.head), sel2.$anchor.sharedDepth(sel2.head));
  return sel1.$anchor.start(depth) != sel2.$anchor.start(depth);
}
function buildNodeViews(view) {
  let result = /* @__PURE__ */ Object.create(null);
  function add(obj) {
    for (let prop in obj)
      if (!Object.prototype.hasOwnProperty.call(result, prop))
        result[prop] = obj[prop];
  }
  view.someProp("nodeViews", add);
  view.someProp("markViews", add);
  return result;
}
function changedNodeViews(a, b) {
  let nA = 0, nB = 0;
  for (let prop in a) {
    if (a[prop] != b[prop])
      return true;
    nA++;
  }
  for (let _ in b)
    nB++;
  return nA != nB;
}
function checkStateComponent(plugin) {
  if (plugin.spec.state || plugin.spec.filterTransaction || plugin.spec.appendTransaction)
    throw new RangeError("Plugins passed directly to the view must not have a state component");
}

// node_modules/.pnpm/prosemirror-commands@1.7.2/node_modules/prosemirror-commands/dist/index.js
var deleteSelection = (state, dispatch) => {
  if (state.selection.empty)
    return false;
  if (dispatch)
    dispatch(state.tr.deleteSelection().scrollIntoView());
  return true;
};
function atBlockStart(state, view) {
  let { $cursor } = state.selection;
  if (!$cursor || (view ? !view.endOfTextblock("backward", state) : $cursor.parentOffset > 0))
    return null;
  return $cursor;
}
var joinBackward = (state, dispatch, view) => {
  let $cursor = atBlockStart(state, view);
  if (!$cursor)
    return false;
  let $cut = findCutBefore($cursor);
  if (!$cut) {
    let range = $cursor.blockRange(), target = range && liftTarget(range);
    if (target == null)
      return false;
    if (dispatch)
      dispatch(state.tr.lift(range, target).scrollIntoView());
    return true;
  }
  let before = $cut.nodeBefore;
  if (deleteBarrier(state, $cut, dispatch, -1))
    return true;
  if ($cursor.parent.content.size == 0 && (textblockAt(before, "end") || NodeSelection.isSelectable(before))) {
    for (let depth = $cursor.depth; ; depth--) {
      let delStep = replaceStep(state.doc, $cursor.before(depth), $cursor.after(depth), Slice.empty);
      if (delStep && delStep.slice.size < delStep.to - delStep.from) {
        if (dispatch) {
          let tr = state.tr.step(delStep);
          tr.setSelection(textblockAt(before, "end") ? Selection.findFrom(tr.doc.resolve(tr.mapping.map($cut.pos, -1)), -1) : NodeSelection.create(tr.doc, $cut.pos - before.nodeSize));
          dispatch(tr.scrollIntoView());
        }
        return true;
      }
      if (depth == 1 || $cursor.node(depth - 1).childCount > 1)
        break;
    }
  }
  if (before.isAtom && $cut.depth == $cursor.depth - 1) {
    if (dispatch)
      dispatch(state.tr.delete($cut.pos - before.nodeSize, $cut.pos).scrollIntoView());
    return true;
  }
  return false;
};
function textblockAt(node2, side, only = false) {
  for (let scan = node2; scan; scan = side == "start" ? scan.firstChild : scan.lastChild) {
    if (scan.isTextblock)
      return true;
    if (only && scan.childCount != 1)
      return false;
  }
  return false;
}
var selectNodeBackward = (state, dispatch, view) => {
  let { $head, empty: empty3 } = state.selection, $cut = $head;
  if (!empty3)
    return false;
  if ($head.parent.isTextblock) {
    if (view ? !view.endOfTextblock("backward", state) : $head.parentOffset > 0)
      return false;
    $cut = findCutBefore($head);
  }
  let node2 = $cut && $cut.nodeBefore;
  if (!node2 || !NodeSelection.isSelectable(node2))
    return false;
  if (dispatch)
    dispatch(state.tr.setSelection(NodeSelection.create(state.doc, $cut.pos - node2.nodeSize)).scrollIntoView());
  return true;
};
function findCutBefore($pos) {
  if (!$pos.parent.type.spec.isolating)
    for (let i2 = $pos.depth - 1; i2 >= 0; i2--) {
      if ($pos.index(i2) > 0)
        return $pos.doc.resolve($pos.before(i2 + 1));
      if ($pos.node(i2).type.spec.isolating)
        break;
    }
  return null;
}
function atBlockEnd(state, view) {
  let { $cursor } = state.selection;
  if (!$cursor || (view ? !view.endOfTextblock("forward", state) : $cursor.parentOffset < $cursor.parent.content.size))
    return null;
  return $cursor;
}
var joinForward = (state, dispatch, view) => {
  let $cursor = atBlockEnd(state, view);
  if (!$cursor)
    return false;
  let $cut = findCutAfter($cursor);
  if (!$cut)
    return false;
  let after = $cut.nodeAfter;
  if (deleteBarrier(state, $cut, dispatch, 1))
    return true;
  if ($cursor.parent.content.size == 0 && (textblockAt(after, "start") || NodeSelection.isSelectable(after))) {
    let delStep = replaceStep(state.doc, $cursor.before(), $cursor.after(), Slice.empty);
    if (delStep && delStep.slice.size < delStep.to - delStep.from) {
      if (dispatch) {
        let tr = state.tr.step(delStep);
        tr.setSelection(textblockAt(after, "start") ? Selection.findFrom(tr.doc.resolve(tr.mapping.map($cut.pos)), 1) : NodeSelection.create(tr.doc, tr.mapping.map($cut.pos)));
        dispatch(tr.scrollIntoView());
      }
      return true;
    }
  }
  if (after.isAtom && $cut.depth == $cursor.depth - 1) {
    if (dispatch)
      dispatch(state.tr.delete($cut.pos, $cut.pos + after.nodeSize).scrollIntoView());
    return true;
  }
  return false;
};
var selectNodeForward = (state, dispatch, view) => {
  let { $head, empty: empty3 } = state.selection, $cut = $head;
  if (!empty3)
    return false;
  if ($head.parent.isTextblock) {
    if (view ? !view.endOfTextblock("forward", state) : $head.parentOffset < $head.parent.content.size)
      return false;
    $cut = findCutAfter($head);
  }
  let node2 = $cut && $cut.nodeAfter;
  if (!node2 || !NodeSelection.isSelectable(node2))
    return false;
  if (dispatch)
    dispatch(state.tr.setSelection(NodeSelection.create(state.doc, $cut.pos)).scrollIntoView());
  return true;
};
function findCutAfter($pos) {
  if (!$pos.parent.type.spec.isolating)
    for (let i2 = $pos.depth - 1; i2 >= 0; i2--) {
      let parent = $pos.node(i2);
      if ($pos.index(i2) + 1 < parent.childCount)
        return $pos.doc.resolve($pos.after(i2 + 1));
      if (parent.type.spec.isolating)
        break;
    }
  return null;
}
var newlineInCode = (state, dispatch) => {
  let { $head, $anchor } = state.selection;
  if (!$head.parent.type.spec.code || !$head.sameParent($anchor))
    return false;
  if (dispatch)
    dispatch(state.tr.insertText("\n").scrollIntoView());
  return true;
};
function defaultBlockAt(match) {
  for (let i2 = 0; i2 < match.edgeCount; i2++) {
    let { type } = match.edge(i2);
    if (type.isTextblock && !type.hasRequiredAttrs())
      return type;
  }
  return null;
}
var exitCode = (state, dispatch) => {
  let { $head, $anchor } = state.selection;
  if (!$head.parent.type.spec.code || !$head.sameParent($anchor))
    return false;
  let above = $head.node(-1), after = $head.indexAfter(-1), type = defaultBlockAt(above.contentMatchAt(after));
  if (!type || !above.canReplaceWith(after, after, type))
    return false;
  if (dispatch) {
    let pos = $head.after(), tr = state.tr.replaceWith(pos, pos, type.createAndFill());
    tr.setSelection(Selection.near(tr.doc.resolve(pos), 1));
    dispatch(tr.scrollIntoView());
  }
  return true;
};
var createParagraphNear = (state, dispatch) => {
  let sel = state.selection, { $from, $to } = sel;
  if (sel instanceof AllSelection || $from.parent.inlineContent || $to.parent.inlineContent)
    return false;
  let type = defaultBlockAt($to.parent.contentMatchAt($to.indexAfter()));
  if (!type || !type.isTextblock)
    return false;
  if (dispatch) {
    let side = (!$from.parentOffset && $to.index() < $to.parent.childCount ? $from : $to).pos;
    let tr = state.tr.insert(side, type.createAndFill());
    tr.setSelection(TextSelection.create(tr.doc, side + 1));
    dispatch(tr.scrollIntoView());
  }
  return true;
};
var liftEmptyBlock = (state, dispatch) => {
  let { $cursor } = state.selection;
  if (!$cursor || $cursor.parent.content.size)
    return false;
  if ($cursor.depth > 1 && $cursor.after() != $cursor.end(-1)) {
    let before = $cursor.before();
    if (canSplit(state.doc, before)) {
      if (dispatch)
        dispatch(state.tr.split(before).scrollIntoView());
      return true;
    }
  }
  let range = $cursor.blockRange(), target = range && liftTarget(range);
  if (target == null)
    return false;
  if (dispatch)
    dispatch(state.tr.lift(range, target).scrollIntoView());
  return true;
};
function splitBlockAs(splitNode) {
  return (state, dispatch) => {
    if (state.selection instanceof NodeSelection && state.selection.node.isBlock) {
      let { $from: $from2 } = state.selection;
      if (!$from2.parentOffset || !canSplit(state.doc, $from2.pos))
        return false;
      if (dispatch)
        dispatch(state.tr.split($from2.pos).scrollIntoView());
      return true;
    }
    if (!state.selection.$from.depth)
      return false;
    let tr = state.tr;
    if (!state.selection.empty && (state.selection instanceof TextSelection || state.selection instanceof AllSelection))
      tr.deleteSelection();
    let { $from } = tr.selection, mapFrom = tr.steps.length;
    let types = [];
    let splitDepth, deflt, atEnd = false, atStart = false;
    for (let d = $from.depth; ; d--) {
      let node2 = $from.node(d);
      if (node2.isBlock) {
        atEnd = $from.end(d) == $from.pos + ($from.depth - d);
        atStart = $from.start(d) == $from.pos - ($from.depth - d);
        deflt = defaultBlockAt($from.node(d - 1).contentMatchAt($from.indexAfter(d - 1)));
        let splitType = splitNode && splitNode($from.parent, atEnd, $from);
        types.unshift(splitType || (atEnd && deflt ? { type: deflt } : null));
        splitDepth = d;
        break;
      } else {
        if (d == 1)
          return false;
        types.unshift(null);
      }
    }
    let splitPos = $from.pos;
    let can = canSplit(tr.doc, splitPos, types.length, types);
    if (!can) {
      types[0] = deflt ? { type: deflt } : null;
      can = canSplit(tr.doc, splitPos, types.length, types);
    }
    if (!can)
      return false;
    tr.split(splitPos, types.length, types);
    if (!atEnd && atStart && $from.node(splitDepth).type != deflt) {
      let mapping = tr.mapping.slice(mapFrom);
      let first = mapping.map($from.before(splitDepth)), $first = tr.doc.resolve(first);
      if (deflt && $from.node(splitDepth - 1).canReplaceWith($first.index(), $first.index() + 1, deflt))
        tr.setNodeMarkup(mapping.map($from.before(splitDepth)), deflt);
    }
    if (dispatch)
      dispatch(tr.scrollIntoView());
    return true;
  };
}
var splitBlock = splitBlockAs();
var selectAll = (state, dispatch) => {
  if (dispatch)
    dispatch(state.tr.setSelection(new AllSelection(state.doc)));
  return true;
};
function joinMaybeClear(state, $pos, dispatch) {
  let before = $pos.nodeBefore, after = $pos.nodeAfter, index2 = $pos.index();
  if (!before || !after || !before.type.compatibleContent(after.type))
    return false;
  if (!before.content.size && $pos.parent.canReplace(index2 - 1, index2)) {
    if (dispatch)
      dispatch(state.tr.delete($pos.pos - before.nodeSize, $pos.pos).scrollIntoView());
    return true;
  }
  if (!$pos.parent.canReplace(index2, index2 + 1) || !(after.isTextblock || canJoin(state.doc, $pos.pos)))
    return false;
  if (dispatch)
    dispatch(state.tr.join($pos.pos).scrollIntoView());
  return true;
}
function deleteBarrier(state, $cut, dispatch, dir) {
  let before = $cut.nodeBefore, after = $cut.nodeAfter, conn, match;
  let isolated = before.type.spec.isolating || after.type.spec.isolating;
  if (!isolated && joinMaybeClear(state, $cut, dispatch))
    return true;
  let canDelAfter = !isolated && $cut.parent.canReplace($cut.index(), $cut.index() + 1);
  if (canDelAfter && (conn = (match = before.contentMatchAt(before.childCount)).findWrapping(after.type)) && match.matchType(conn[0] || after.type).validEnd) {
    if (dispatch) {
      let end = $cut.pos + after.nodeSize, wrap2 = Fragment.empty;
      for (let i2 = conn.length - 1; i2 >= 0; i2--)
        wrap2 = Fragment.from(conn[i2].create(null, wrap2));
      wrap2 = Fragment.from(before.copy(wrap2));
      let tr = state.tr.step(new ReplaceAroundStep($cut.pos - 1, end, $cut.pos, end, new Slice(wrap2, 1, 0), conn.length, true));
      let $joinAt = tr.doc.resolve(end + 2 * conn.length);
      if ($joinAt.nodeAfter && $joinAt.nodeAfter.type == before.type && canJoin(tr.doc, $joinAt.pos))
        tr.join($joinAt.pos);
      dispatch(tr.scrollIntoView());
    }
    return true;
  }
  let selAfter = after.type.spec.isolating || dir > 0 && isolated ? null : Selection.findFrom($cut, 1);
  let range = selAfter && selAfter.$from.blockRange(selAfter.$to), target = range && liftTarget(range);
  if (target != null && target >= $cut.depth) {
    if (dispatch)
      dispatch(state.tr.lift(range, target).scrollIntoView());
    return true;
  }
  if (canDelAfter && textblockAt(after, "start", true) && textblockAt(before, "end")) {
    let at = before, wrap2 = [];
    for (; ; ) {
      wrap2.push(at);
      if (at.isTextblock)
        break;
      at = at.lastChild;
    }
    let afterText = after, afterDepth = 1;
    for (; !afterText.isTextblock; afterText = afterText.firstChild)
      afterDepth++;
    if (at.canReplace(at.childCount, at.childCount, afterText.content)) {
      if (dispatch) {
        let end = Fragment.empty;
        for (let i2 = wrap2.length - 1; i2 >= 0; i2--)
          end = Fragment.from(wrap2[i2].copy(end));
        let tr = state.tr.step(new ReplaceAroundStep($cut.pos - wrap2.length, $cut.pos + after.nodeSize, $cut.pos + afterDepth, $cut.pos + after.nodeSize - afterDepth, new Slice(end, wrap2.length, 0), 0, true));
        dispatch(tr.scrollIntoView());
      }
      return true;
    }
  }
  return false;
}
function selectTextblockSide(side) {
  return function(state, dispatch) {
    let sel = state.selection, $pos = side < 0 ? sel.$from : sel.$to;
    let depth = $pos.depth;
    while ($pos.node(depth).isInline) {
      if (!depth)
        return false;
      depth--;
    }
    if (!$pos.node(depth).isTextblock)
      return false;
    if (dispatch)
      dispatch(state.tr.setSelection(TextSelection.create(state.doc, side < 0 ? $pos.start(depth) : $pos.end(depth))));
    return true;
  };
}
var selectTextblockStart = selectTextblockSide(-1);
var selectTextblockEnd = selectTextblockSide(1);
function markApplies(doc3, ranges, type, enterAtoms) {
  for (let i2 = 0; i2 < ranges.length; i2++) {
    let { $from, $to } = ranges[i2];
    let can = $from.depth == 0 ? doc3.inlineContent && doc3.type.allowsMarkType(type) : false;
    doc3.nodesBetween($from.pos, $to.pos, (node2, pos) => {
      if (can || !enterAtoms && node2.isAtom && node2.isInline && pos >= $from.pos && pos + node2.nodeSize <= $to.pos)
        return false;
      can = node2.inlineContent && node2.type.allowsMarkType(type);
    });
    if (can)
      return true;
  }
  return false;
}
function removeInlineAtoms(ranges) {
  let result = [];
  for (let i2 = 0; i2 < ranges.length; i2++) {
    let { $from, $to } = ranges[i2];
    $from.doc.nodesBetween($from.pos, $to.pos, (node2, pos) => {
      if (node2.isAtom && node2.content.size && node2.isInline && pos >= $from.pos && pos + node2.nodeSize <= $to.pos) {
        if (pos + 1 > $from.pos)
          result.push(new SelectionRange($from, $from.doc.resolve(pos + 1)));
        $from = $from.doc.resolve(pos + 1 + node2.content.size);
        return false;
      }
    });
    if ($from.pos < $to.pos)
      result.push(new SelectionRange($from, $to));
  }
  return result;
}
function toggleMark(markType, attrs = null, options) {
  let removeWhenPresent = (options && options.removeWhenPresent) !== false;
  let enterAtoms = (options && options.enterInlineAtoms) !== false;
  let dropSpace = !(options && options.includeWhitespace);
  return function(state, dispatch) {
    let { empty: empty3, $cursor, ranges } = state.selection;
    if (empty3 && !$cursor || !markApplies(state.doc, ranges, markType, enterAtoms))
      return false;
    if (dispatch) {
      if ($cursor) {
        if (markType.isInSet(state.storedMarks || $cursor.marks()))
          dispatch(state.tr.removeStoredMark(markType));
        else
          dispatch(state.tr.addStoredMark(markType.create(attrs)));
      } else {
        let add, tr = state.tr;
        if (!enterAtoms)
          ranges = removeInlineAtoms(ranges);
        if (removeWhenPresent) {
          add = !ranges.some((r) => state.doc.rangeHasMark(r.$from.pos, r.$to.pos, markType));
        } else {
          add = !ranges.every((r) => {
            let missing = false;
            tr.doc.nodesBetween(r.$from.pos, r.$to.pos, (node2, pos, parent) => {
              if (missing)
                return false;
              missing = !markType.isInSet(node2.marks) && !!parent && parent.type.allowsMarkType(markType) && !(node2.isText && /^\s*$/.test(node2.textBetween(Math.max(0, r.$from.pos - pos), Math.min(node2.nodeSize, r.$to.pos - pos))));
            });
            return !missing;
          });
        }
        for (let i2 = 0; i2 < ranges.length; i2++) {
          let { $from, $to } = ranges[i2];
          if (!add) {
            tr.removeMark($from.pos, $to.pos, markType);
          } else {
            let from2 = $from.pos, to = $to.pos, start = $from.nodeAfter, end = $to.nodeBefore;
            let spaceStart = dropSpace && start && start.isText ? /^\s*/.exec(start.text)[0].length : 0;
            let spaceEnd = dropSpace && end && end.isText ? /\s*$/.exec(end.text)[0].length : 0;
            if (from2 + spaceStart < to) {
              from2 += spaceStart;
              to -= spaceEnd;
            }
            tr.addMark(from2, to, markType.create(attrs));
          }
        }
        dispatch(tr.scrollIntoView());
      }
    }
    return true;
  };
}
function chainCommands(...commands) {
  return function(state, dispatch, view) {
    for (let i2 = 0; i2 < commands.length; i2++)
      if (commands[i2](state, dispatch, view))
        return true;
    return false;
  };
}
var backspace = chainCommands(deleteSelection, joinBackward, selectNodeBackward);
var del = chainCommands(deleteSelection, joinForward, selectNodeForward);
var pcBaseKeymap = {
  "Enter": chainCommands(newlineInCode, createParagraphNear, liftEmptyBlock, splitBlock),
  "Mod-Enter": exitCode,
  "Backspace": backspace,
  "Mod-Backspace": backspace,
  "Shift-Backspace": backspace,
  "Delete": del,
  "Mod-Delete": del,
  "Mod-a": selectAll
};
var macBaseKeymap = {
  "Ctrl-h": pcBaseKeymap["Backspace"],
  "Alt-Backspace": pcBaseKeymap["Mod-Backspace"],
  "Ctrl-d": pcBaseKeymap["Delete"],
  "Ctrl-Alt-Backspace": pcBaseKeymap["Mod-Delete"],
  "Alt-Delete": pcBaseKeymap["Mod-Delete"],
  "Alt-d": pcBaseKeymap["Mod-Delete"],
  "Ctrl-a": selectTextblockStart,
  "Ctrl-e": selectTextblockEnd
};
for (let key2 in pcBaseKeymap)
  macBaseKeymap[key2] = pcBaseKeymap[key2];
var mac2 = typeof navigator != "undefined" ? /Mac|iP(hone|[oa]d)/.test(navigator.platform) : typeof os != "undefined" && os.platform ? os.platform() == "darwin" : false;
var baseKeymap = mac2 ? macBaseKeymap : pcBaseKeymap;

// node_modules/.pnpm/rope-sequence@1.3.4/node_modules/rope-sequence/dist/index.js
var GOOD_LEAF_SIZE = 200;
var RopeSequence = function RopeSequence2() {
};
RopeSequence.prototype.append = function append(other) {
  if (!other.length) {
    return this;
  }
  other = RopeSequence.from(other);
  return !this.length && other || other.length < GOOD_LEAF_SIZE && this.leafAppend(other) || this.length < GOOD_LEAF_SIZE && other.leafPrepend(this) || this.appendInner(other);
};
RopeSequence.prototype.prepend = function prepend(other) {
  if (!other.length) {
    return this;
  }
  return RopeSequence.from(other).append(this);
};
RopeSequence.prototype.appendInner = function appendInner(other) {
  return new Append(this, other);
};
RopeSequence.prototype.slice = function slice(from2, to) {
  if (from2 === void 0) from2 = 0;
  if (to === void 0) to = this.length;
  if (from2 >= to) {
    return RopeSequence.empty;
  }
  return this.sliceInner(Math.max(0, from2), Math.min(this.length, to));
};
RopeSequence.prototype.get = function get(i2) {
  if (i2 < 0 || i2 >= this.length) {
    return void 0;
  }
  return this.getInner(i2);
};
RopeSequence.prototype.forEach = function forEach(f, from2, to) {
  if (from2 === void 0) from2 = 0;
  if (to === void 0) to = this.length;
  if (from2 <= to) {
    this.forEachInner(f, from2, to, 0);
  } else {
    this.forEachInvertedInner(f, from2, to, 0);
  }
};
RopeSequence.prototype.map = function map(f, from2, to) {
  if (from2 === void 0) from2 = 0;
  if (to === void 0) to = this.length;
  var result = [];
  this.forEach(function(elt, i2) {
    return result.push(f(elt, i2));
  }, from2, to);
  return result;
};
RopeSequence.from = function from(values) {
  if (values instanceof RopeSequence) {
    return values;
  }
  return values && values.length ? new Leaf(values) : RopeSequence.empty;
};
var Leaf = /* @__PURE__ */ (function(RopeSequence3) {
  function Leaf2(values) {
    RopeSequence3.call(this);
    this.values = values;
  }
  if (RopeSequence3) Leaf2.__proto__ = RopeSequence3;
  Leaf2.prototype = Object.create(RopeSequence3 && RopeSequence3.prototype);
  Leaf2.prototype.constructor = Leaf2;
  var prototypeAccessors = { length: { configurable: true }, depth: { configurable: true } };
  Leaf2.prototype.flatten = function flatten() {
    return this.values;
  };
  Leaf2.prototype.sliceInner = function sliceInner(from2, to) {
    if (from2 == 0 && to == this.length) {
      return this;
    }
    return new Leaf2(this.values.slice(from2, to));
  };
  Leaf2.prototype.getInner = function getInner(i2) {
    return this.values[i2];
  };
  Leaf2.prototype.forEachInner = function forEachInner(f, from2, to, start) {
    for (var i2 = from2; i2 < to; i2++) {
      if (f(this.values[i2], start + i2) === false) {
        return false;
      }
    }
  };
  Leaf2.prototype.forEachInvertedInner = function forEachInvertedInner(f, from2, to, start) {
    for (var i2 = from2 - 1; i2 >= to; i2--) {
      if (f(this.values[i2], start + i2) === false) {
        return false;
      }
    }
  };
  Leaf2.prototype.leafAppend = function leafAppend(other) {
    if (this.length + other.length <= GOOD_LEAF_SIZE) {
      return new Leaf2(this.values.concat(other.flatten()));
    }
  };
  Leaf2.prototype.leafPrepend = function leafPrepend(other) {
    if (this.length + other.length <= GOOD_LEAF_SIZE) {
      return new Leaf2(other.flatten().concat(this.values));
    }
  };
  prototypeAccessors.length.get = function() {
    return this.values.length;
  };
  prototypeAccessors.depth.get = function() {
    return 0;
  };
  Object.defineProperties(Leaf2.prototype, prototypeAccessors);
  return Leaf2;
})(RopeSequence);
RopeSequence.empty = new Leaf([]);
var Append = /* @__PURE__ */ (function(RopeSequence3) {
  function Append2(left, right) {
    RopeSequence3.call(this);
    this.left = left;
    this.right = right;
    this.length = left.length + right.length;
    this.depth = Math.max(left.depth, right.depth) + 1;
  }
  if (RopeSequence3) Append2.__proto__ = RopeSequence3;
  Append2.prototype = Object.create(RopeSequence3 && RopeSequence3.prototype);
  Append2.prototype.constructor = Append2;
  Append2.prototype.flatten = function flatten() {
    return this.left.flatten().concat(this.right.flatten());
  };
  Append2.prototype.getInner = function getInner(i2) {
    return i2 < this.left.length ? this.left.get(i2) : this.right.get(i2 - this.left.length);
  };
  Append2.prototype.forEachInner = function forEachInner(f, from2, to, start) {
    var leftLen = this.left.length;
    if (from2 < leftLen && this.left.forEachInner(f, from2, Math.min(to, leftLen), start) === false) {
      return false;
    }
    if (to > leftLen && this.right.forEachInner(f, Math.max(from2 - leftLen, 0), Math.min(this.length, to) - leftLen, start + leftLen) === false) {
      return false;
    }
  };
  Append2.prototype.forEachInvertedInner = function forEachInvertedInner(f, from2, to, start) {
    var leftLen = this.left.length;
    if (from2 > leftLen && this.right.forEachInvertedInner(f, from2 - leftLen, Math.max(to, leftLen) - leftLen, start + leftLen) === false) {
      return false;
    }
    if (to < leftLen && this.left.forEachInvertedInner(f, Math.min(from2, leftLen), to, start) === false) {
      return false;
    }
  };
  Append2.prototype.sliceInner = function sliceInner(from2, to) {
    if (from2 == 0 && to == this.length) {
      return this;
    }
    var leftLen = this.left.length;
    if (to <= leftLen) {
      return this.left.slice(from2, to);
    }
    if (from2 >= leftLen) {
      return this.right.slice(from2 - leftLen, to - leftLen);
    }
    return this.left.slice(from2, leftLen).append(this.right.slice(0, to - leftLen));
  };
  Append2.prototype.leafAppend = function leafAppend(other) {
    var inner = this.right.leafAppend(other);
    if (inner) {
      return new Append2(this.left, inner);
    }
  };
  Append2.prototype.leafPrepend = function leafPrepend(other) {
    var inner = this.left.leafPrepend(other);
    if (inner) {
      return new Append2(inner, this.right);
    }
  };
  Append2.prototype.appendInner = function appendInner2(other) {
    if (this.left.depth >= Math.max(this.right.depth, other.depth) + 1) {
      return new Append2(this.left, new Append2(this.right, other));
    }
    return new Append2(this, other);
  };
  return Append2;
})(RopeSequence);
var dist_default2 = RopeSequence;

// node_modules/.pnpm/prosemirror-history@1.5.1/node_modules/prosemirror-history/dist/index.js
var max_empty_items = 500;
var Branch = class _Branch {
  constructor(items, eventCount) {
    this.items = items;
    this.eventCount = eventCount;
  }
  // Pop the latest event off the branch's history and apply it
  // to a document transform.
  popEvent(state, preserveItems) {
    if (this.eventCount == 0)
      return null;
    let end = this.items.length;
    for (; ; end--) {
      let next = this.items.get(end - 1);
      if (next.selection) {
        --end;
        break;
      }
    }
    let remap, mapFrom;
    if (preserveItems) {
      remap = this.remapping(end, this.items.length);
      mapFrom = remap.maps.length;
    }
    let transform = state.tr;
    let selection, remaining;
    let addAfter = [], addBefore = [];
    this.items.forEach((item, i2) => {
      if (!item.step) {
        if (!remap) {
          remap = this.remapping(end, i2 + 1);
          mapFrom = remap.maps.length;
        }
        mapFrom--;
        addBefore.push(item);
        return;
      }
      if (remap) {
        addBefore.push(new Item(item.map));
        let step = item.step.map(remap.slice(mapFrom)), map5;
        if (step && transform.maybeStep(step).doc) {
          map5 = transform.mapping.maps[transform.mapping.maps.length - 1];
          addAfter.push(new Item(map5, void 0, void 0, addAfter.length + addBefore.length));
        }
        mapFrom--;
        if (map5)
          remap.appendMap(map5, mapFrom);
      } else {
        transform.maybeStep(item.step);
      }
      if (item.selection) {
        selection = remap ? item.selection.map(remap.slice(mapFrom)) : item.selection;
        remaining = new _Branch(this.items.slice(0, end).append(addBefore.reverse().concat(addAfter)), this.eventCount - 1);
        return false;
      }
    }, this.items.length, 0);
    return { remaining, transform, selection };
  }
  // Create a new branch with the given transform added.
  addTransform(transform, selection, histOptions, preserveItems) {
    let newItems = [], eventCount = this.eventCount;
    let oldItems = this.items, lastItem = !preserveItems && oldItems.length ? oldItems.get(oldItems.length - 1) : null;
    for (let i2 = 0; i2 < transform.steps.length; i2++) {
      let step = transform.steps[i2].invert(transform.docs[i2]);
      let item = new Item(transform.mapping.maps[i2], step, selection), merged;
      if (merged = lastItem && lastItem.merge(item)) {
        item = merged;
        if (i2)
          newItems.pop();
        else
          oldItems = oldItems.slice(0, oldItems.length - 1);
      }
      newItems.push(item);
      if (selection) {
        eventCount++;
        selection = void 0;
      }
      if (!preserveItems)
        lastItem = item;
    }
    let overflow = eventCount - histOptions.depth;
    if (overflow > DEPTH_OVERFLOW) {
      oldItems = cutOffEvents(oldItems, overflow);
      eventCount -= overflow;
    }
    return new _Branch(oldItems.append(newItems), eventCount);
  }
  remapping(from2, to) {
    let maps = new Mapping();
    this.items.forEach((item, i2) => {
      let mirrorPos = item.mirrorOffset != null && i2 - item.mirrorOffset >= from2 ? maps.maps.length - item.mirrorOffset : void 0;
      maps.appendMap(item.map, mirrorPos);
    }, from2, to);
    return maps;
  }
  addMaps(array) {
    if (this.eventCount == 0)
      return this;
    return new _Branch(this.items.append(array.map((map5) => new Item(map5))), this.eventCount);
  }
  // When the collab module receives remote changes, the history has
  // to know about those, so that it can adjust the steps that were
  // rebased on top of the remote changes, and include the position
  // maps for the remote changes in its array of items.
  rebased(rebasedTransform, rebasedCount) {
    if (!this.eventCount)
      return this;
    rebasedCount = Math.min(this.items.length, rebasedCount);
    let rebasedItems = [], start = this.items.length - rebasedCount;
    let mapping = rebasedTransform.mapping;
    let newUntil = rebasedTransform.steps.length;
    let eventCount = this.eventCount;
    this.items.forEach((item) => {
      if (item.selection)
        eventCount--;
    }, start);
    let iRebased = rebasedCount;
    this.items.forEach((item) => {
      let pos = mapping.getMirror(--iRebased);
      if (pos == null)
        return;
      newUntil = Math.min(newUntil, pos);
      let map5 = mapping.maps[pos];
      if (item.step) {
        let step = rebasedTransform.steps[pos].invert(rebasedTransform.docs[pos]);
        let selection = item.selection && item.selection.map(mapping.slice(iRebased + 1, pos));
        if (selection)
          eventCount++;
        rebasedItems.push(new Item(map5, step, selection));
      } else {
        rebasedItems.push(new Item(map5));
      }
    }, start);
    let newMaps = [];
    for (let i2 = rebasedCount; i2 < newUntil; i2++)
      newMaps.push(new Item(mapping.maps[i2]));
    let items = this.items.slice(0, start).append(newMaps).append(rebasedItems);
    let branch = new _Branch(items, eventCount);
    if (branch.emptyItemCount() > max_empty_items)
      branch = branch.compress(this.items.length - rebasedItems.length);
    return branch;
  }
  emptyItemCount() {
    let count = 0;
    this.items.forEach((item) => {
      if (!item.step)
        count++;
    });
    return count;
  }
  // Compressing a branch means rewriting it to push the air (map-only
  // items) out. During collaboration, these naturally accumulate
  // because each remote change adds one. The `upto` argument is used
  // to ensure that only the items below a given level are compressed,
  // because `rebased` relies on a clean, untouched set of items in
  // order to associate old items with rebased steps.
  compress(upto = this.items.length) {
    let remap = this.remapping(0, upto), mapFrom = remap.maps.length;
    let items = [], events = 0;
    this.items.forEach((item, i2) => {
      if (i2 >= upto) {
        items.push(item);
        if (item.selection)
          events++;
      } else if (item.step) {
        let step = item.step.map(remap.slice(mapFrom)), map5 = step && step.getMap();
        mapFrom--;
        if (map5)
          remap.appendMap(map5, mapFrom);
        if (step) {
          let selection = item.selection && item.selection.map(remap.slice(mapFrom));
          if (selection)
            events++;
          let newItem = new Item(map5.invert(), step, selection), merged, last = items.length - 1;
          if (merged = items.length && items[last].merge(newItem))
            items[last] = merged;
          else
            items.push(newItem);
        }
      } else if (item.map) {
        mapFrom--;
      }
    }, this.items.length, 0);
    return new _Branch(dist_default2.from(items.reverse()), events);
  }
};
Branch.empty = new Branch(dist_default2.empty, 0);
function cutOffEvents(items, n) {
  let cutPoint;
  items.forEach((item, i2) => {
    if (item.selection && n-- == 0) {
      cutPoint = i2;
      return false;
    }
  });
  return items.slice(cutPoint);
}
var Item = class _Item {
  constructor(map5, step, selection, mirrorOffset) {
    this.map = map5;
    this.step = step;
    this.selection = selection;
    this.mirrorOffset = mirrorOffset;
  }
  merge(other) {
    if (this.step && other.step && !other.selection) {
      let step = other.step.merge(this.step);
      if (step)
        return new _Item(step.getMap().invert(), step, this.selection);
    }
  }
};
var HistoryState = class {
  constructor(done, undone, prevRanges, prevTime, prevComposition) {
    this.done = done;
    this.undone = undone;
    this.prevRanges = prevRanges;
    this.prevTime = prevTime;
    this.prevComposition = prevComposition;
  }
};
var DEPTH_OVERFLOW = 20;
function applyTransaction(history2, state, tr, options) {
  let historyTr = tr.getMeta(historyKey), rebased;
  if (historyTr)
    return historyTr.historyState;
  if (tr.getMeta(closeHistoryKey))
    history2 = new HistoryState(history2.done, history2.undone, null, 0, -1);
  let appended = tr.getMeta("appendedTransaction");
  if (tr.steps.length == 0) {
    return history2;
  } else if (appended && appended.getMeta(historyKey)) {
    if (appended.getMeta(historyKey).redo)
      return new HistoryState(history2.done.addTransform(tr, void 0, options, mustPreserveItems(state)), history2.undone, rangesFor(tr.mapping.maps), history2.prevTime, history2.prevComposition);
    else
      return new HistoryState(history2.done, history2.undone.addTransform(tr, void 0, options, mustPreserveItems(state)), null, history2.prevTime, history2.prevComposition);
  } else if (tr.getMeta("addToHistory") !== false && !(appended && appended.getMeta("addToHistory") === false)) {
    let composition = tr.getMeta("composition");
    let newGroup = history2.prevTime == 0 || !appended && history2.prevComposition != composition && (history2.prevTime < (tr.time || 0) - options.newGroupDelay || !isAdjacentTo(tr, history2.prevRanges));
    let prevRanges = appended ? mapRanges(history2.prevRanges, tr.mapping) : rangesFor(tr.mapping.maps);
    return new HistoryState(history2.done.addTransform(tr, newGroup ? state.selection.getBookmark() : void 0, options, mustPreserveItems(state)), Branch.empty, prevRanges, tr.time, composition == null ? history2.prevComposition : composition);
  } else if (rebased = tr.getMeta("rebased")) {
    return new HistoryState(history2.done.rebased(tr, rebased), history2.undone.rebased(tr, rebased), mapRanges(history2.prevRanges, tr.mapping), history2.prevTime, history2.prevComposition);
  } else {
    return new HistoryState(history2.done.addMaps(tr.mapping.maps), history2.undone.addMaps(tr.mapping.maps), mapRanges(history2.prevRanges, tr.mapping), history2.prevTime, history2.prevComposition);
  }
}
function isAdjacentTo(transform, prevRanges) {
  if (!prevRanges)
    return false;
  if (!transform.docChanged)
    return true;
  let adjacent = false;
  transform.mapping.maps[0].forEach((start, end) => {
    for (let i2 = 0; i2 < prevRanges.length; i2 += 2)
      if (start <= prevRanges[i2 + 1] && end >= prevRanges[i2])
        adjacent = true;
  });
  return adjacent;
}
function rangesFor(maps) {
  let result = [];
  for (let i2 = maps.length - 1; i2 >= 0 && result.length == 0; i2--)
    maps[i2].forEach((_from, _to, from2, to) => result.push(from2, to));
  return result;
}
function mapRanges(ranges, mapping) {
  if (!ranges)
    return null;
  let result = [];
  for (let i2 = 0; i2 < ranges.length; i2 += 2) {
    let from2 = mapping.map(ranges[i2], 1), to = mapping.map(ranges[i2 + 1], -1);
    if (from2 <= to)
      result.push(from2, to);
  }
  return result;
}
function histTransaction(history2, state, redo2) {
  let preserveItems = mustPreserveItems(state);
  let histOptions = historyKey.get(state).spec.config;
  let pop = (redo2 ? history2.undone : history2.done).popEvent(state, preserveItems);
  if (!pop)
    return null;
  let selection = pop.selection.resolve(pop.transform.doc);
  let added = (redo2 ? history2.done : history2.undone).addTransform(pop.transform, state.selection.getBookmark(), histOptions, preserveItems);
  let newHist = new HistoryState(redo2 ? added : pop.remaining, redo2 ? pop.remaining : added, null, 0, -1);
  return pop.transform.setSelection(selection).setMeta(historyKey, { redo: redo2, historyState: newHist });
}
var cachedPreserveItems = false;
var cachedPreserveItemsPlugins = null;
function mustPreserveItems(state) {
  let plugins = state.plugins;
  if (cachedPreserveItemsPlugins != plugins) {
    cachedPreserveItems = false;
    cachedPreserveItemsPlugins = plugins;
    for (let i2 = 0; i2 < plugins.length; i2++)
      if (plugins[i2].spec.historyPreserveItems) {
        cachedPreserveItems = true;
        break;
      }
  }
  return cachedPreserveItems;
}
function closeHistory(tr) {
  return tr.setMeta(closeHistoryKey, true);
}
var historyKey = new PluginKey("history");
var closeHistoryKey = new PluginKey("closeHistory");
function history(config = {}) {
  config = {
    depth: config.depth || 100,
    newGroupDelay: config.newGroupDelay || 500
  };
  return new Plugin({
    key: historyKey,
    state: {
      init() {
        return new HistoryState(Branch.empty, Branch.empty, null, 0, -1);
      },
      apply(tr, hist, state) {
        return applyTransaction(hist, state, tr, config);
      }
    },
    config,
    props: {
      handleDOMEvents: {
        beforeinput(view, e) {
          let inputType = e.inputType;
          let command = inputType == "historyUndo" ? undo : inputType == "historyRedo" ? redo : null;
          if (!command || !view.editable)
            return false;
          e.preventDefault();
          return command(view.state, view.dispatch);
        }
      }
    }
  });
}
function buildCommand(redo2, scroll) {
  return (state, dispatch) => {
    let hist = historyKey.getState(state);
    if (!hist || (redo2 ? hist.undone : hist.done).eventCount == 0)
      return false;
    if (dispatch) {
      let tr = histTransaction(hist, state, redo2);
      if (tr)
        dispatch(scroll ? tr.scrollIntoView() : tr);
    }
    return true;
  };
}
var undo = buildCommand(false, true);
var redo = buildCommand(true, true);
var undoNoScroll = buildCommand(false, false);
var redoNoScroll = buildCommand(true, false);
function isHistoryTransaction(tr) {
  return tr.getMeta(historyKey) != null;
}

// node_modules/.pnpm/w3c-keyname@2.2.8/node_modules/w3c-keyname/index.js
var base = {
  8: "Backspace",
  9: "Tab",
  10: "Enter",
  12: "NumLock",
  13: "Enter",
  16: "Shift",
  17: "Control",
  18: "Alt",
  20: "CapsLock",
  27: "Escape",
  32: " ",
  33: "PageUp",
  34: "PageDown",
  35: "End",
  36: "Home",
  37: "ArrowLeft",
  38: "ArrowUp",
  39: "ArrowRight",
  40: "ArrowDown",
  44: "PrintScreen",
  45: "Insert",
  46: "Delete",
  59: ";",
  61: "=",
  91: "Meta",
  92: "Meta",
  106: "*",
  107: "+",
  108: ",",
  109: "-",
  110: ".",
  111: "/",
  144: "NumLock",
  145: "ScrollLock",
  160: "Shift",
  161: "Shift",
  162: "Control",
  163: "Control",
  164: "Alt",
  165: "Alt",
  173: "-",
  186: ";",
  187: "=",
  188: ",",
  189: "-",
  190: ".",
  191: "/",
  192: "`",
  219: "[",
  220: "\\",
  221: "]",
  222: "'"
};
var shift = {
  48: ")",
  49: "!",
  50: "@",
  51: "#",
  52: "$",
  53: "%",
  54: "^",
  55: "&",
  56: "*",
  57: "(",
  59: ":",
  61: "+",
  173: "_",
  186: ":",
  187: "+",
  188: "<",
  189: "_",
  190: ">",
  191: "?",
  192: "~",
  219: "{",
  220: "|",
  221: "}",
  222: '"'
};
var mac3 = typeof navigator != "undefined" && /Mac/.test(navigator.platform);
var ie2 = typeof navigator != "undefined" && /MSIE \d|Trident\/(?:[7-9]|\d{2,})\..*rv:(\d+)/.exec(navigator.userAgent);
for (i = 0; i < 10; i++) base[48 + i] = base[96 + i] = String(i);
var i;
for (i = 1; i <= 24; i++) base[i + 111] = "F" + i;
var i;
for (i = 65; i <= 90; i++) {
  base[i] = String.fromCharCode(i + 32);
  shift[i] = String.fromCharCode(i);
}
var i;
for (code in base) if (!shift.hasOwnProperty(code)) shift[code] = base[code];
var code;
function keyName(event) {
  var ignoreKey = mac3 && event.metaKey && event.shiftKey && !event.ctrlKey && !event.altKey || ie2 && event.shiftKey && event.key && event.key.length == 1 || event.key == "Unidentified";
  var name = !ignoreKey && event.key || (event.shiftKey ? shift : base)[event.keyCode] || event.key || "Unidentified";
  if (name == "Esc") name = "Escape";
  if (name == "Del") name = "Delete";
  if (name == "Left") name = "ArrowLeft";
  if (name == "Up") name = "ArrowUp";
  if (name == "Right") name = "ArrowRight";
  if (name == "Down") name = "ArrowDown";
  return name;
}

// node_modules/.pnpm/prosemirror-keymap@1.2.3/node_modules/prosemirror-keymap/dist/index.js
var mac4 = typeof navigator != "undefined" && /Mac|iP(hone|[oa]d)/.test(navigator.platform);
var windows2 = typeof navigator != "undefined" && /Win/.test(navigator.platform);
function normalizeKeyName(name) {
  let parts = name.split(/-(?!$)/), result = parts[parts.length - 1];
  if (result == "Space")
    result = " ";
  let alt, ctrl, shift2, meta;
  for (let i2 = 0; i2 < parts.length - 1; i2++) {
    let mod = parts[i2];
    if (/^(cmd|meta|m)$/i.test(mod))
      meta = true;
    else if (/^a(lt)?$/i.test(mod))
      alt = true;
    else if (/^(c|ctrl|control)$/i.test(mod))
      ctrl = true;
    else if (/^s(hift)?$/i.test(mod))
      shift2 = true;
    else if (/^mod$/i.test(mod)) {
      if (mac4)
        meta = true;
      else
        ctrl = true;
    } else
      throw new Error("Unrecognized modifier name: " + mod);
  }
  if (alt)
    result = "Alt-" + result;
  if (ctrl)
    result = "Ctrl-" + result;
  if (meta)
    result = "Meta-" + result;
  if (shift2)
    result = "Shift-" + result;
  return result;
}
function normalize(map5) {
  let copy2 = /* @__PURE__ */ Object.create(null);
  for (let prop in map5)
    copy2[normalizeKeyName(prop)] = map5[prop];
  return copy2;
}
function modifiers(name, event, shift2 = true) {
  if (event.altKey)
    name = "Alt-" + name;
  if (event.ctrlKey)
    name = "Ctrl-" + name;
  if (event.metaKey)
    name = "Meta-" + name;
  if (shift2 && event.shiftKey)
    name = "Shift-" + name;
  return name;
}
function keymap(bindings) {
  return new Plugin({ props: { handleKeyDown: keydownHandler(bindings) } });
}
function keydownHandler(bindings) {
  let map5 = normalize(bindings);
  return function(view, event) {
    let name = keyName(event), baseName, direct = map5[modifiers(name, event)];
    if (direct && direct(view.state, view.dispatch, view))
      return true;
    if (name.length == 1 && name != " ") {
      if (event.shiftKey) {
        let noShift = map5[modifiers(name, event, false)];
        if (noShift && noShift(view.state, view.dispatch, view))
          return true;
      }
      if ((event.altKey || event.metaKey || event.ctrlKey) && // Ctrl-Alt may be used for AltGr on Windows
      !(windows2 && event.ctrlKey && event.altKey) && (baseName = base[event.keyCode]) && baseName != name) {
        let fromCode = map5[modifiers(baseName, event)];
        if (fromCode && fromCode(view.state, view.dispatch, view))
          return true;
      }
    }
    return false;
  };
}

// node_modules/.pnpm/mdast-util-to-string@4.0.0/node_modules/mdast-util-to-string/lib/index.js
var emptyOptions = {};
function toString(value, options) {
  const settings = options || emptyOptions;
  const includeImageAlt = typeof settings.includeImageAlt === "boolean" ? settings.includeImageAlt : true;
  const includeHtml = typeof settings.includeHtml === "boolean" ? settings.includeHtml : true;
  return one(value, includeImageAlt, includeHtml);
}
function one(value, includeImageAlt, includeHtml) {
  if (node(value)) {
    if ("value" in value) {
      return value.type === "html" && !includeHtml ? "" : value.value;
    }
    if (includeImageAlt && "alt" in value && value.alt) {
      return value.alt;
    }
    if ("children" in value) {
      return all(value.children, includeImageAlt, includeHtml);
    }
  }
  if (Array.isArray(value)) {
    return all(value, includeImageAlt, includeHtml);
  }
  return "";
}
function all(values, includeImageAlt, includeHtml) {
  const result = [];
  let index2 = -1;
  while (++index2 < values.length) {
    result[index2] = one(values[index2], includeImageAlt, includeHtml);
  }
  return result.join("");
}
function node(value) {
  return Boolean(value && typeof value === "object");
}

// node_modules/.pnpm/character-entities@2.0.2/node_modules/character-entities/index.js
var characterEntities = {
  AElig: "Æ",
  AMP: "&",
  Aacute: "Á",
  Abreve: "Ă",
  Acirc: "Â",
  Acy: "А",
  Afr: "𝔄",
  Agrave: "À",
  Alpha: "Α",
  Amacr: "Ā",
  And: "⩓",
  Aogon: "Ą",
  Aopf: "𝔸",
  ApplyFunction: "⁡",
  Aring: "Å",
  Ascr: "𝒜",
  Assign: "≔",
  Atilde: "Ã",
  Auml: "Ä",
  Backslash: "∖",
  Barv: "⫧",
  Barwed: "⌆",
  Bcy: "Б",
  Because: "∵",
  Bernoullis: "ℬ",
  Beta: "Β",
  Bfr: "𝔅",
  Bopf: "𝔹",
  Breve: "˘",
  Bscr: "ℬ",
  Bumpeq: "≎",
  CHcy: "Ч",
  COPY: "©",
  Cacute: "Ć",
  Cap: "⋒",
  CapitalDifferentialD: "ⅅ",
  Cayleys: "ℭ",
  Ccaron: "Č",
  Ccedil: "Ç",
  Ccirc: "Ĉ",
  Cconint: "∰",
  Cdot: "Ċ",
  Cedilla: "¸",
  CenterDot: "·",
  Cfr: "ℭ",
  Chi: "Χ",
  CircleDot: "⊙",
  CircleMinus: "⊖",
  CirclePlus: "⊕",
  CircleTimes: "⊗",
  ClockwiseContourIntegral: "∲",
  CloseCurlyDoubleQuote: "”",
  CloseCurlyQuote: "’",
  Colon: "∷",
  Colone: "⩴",
  Congruent: "≡",
  Conint: "∯",
  ContourIntegral: "∮",
  Copf: "ℂ",
  Coproduct: "∐",
  CounterClockwiseContourIntegral: "∳",
  Cross: "⨯",
  Cscr: "𝒞",
  Cup: "⋓",
  CupCap: "≍",
  DD: "ⅅ",
  DDotrahd: "⤑",
  DJcy: "Ђ",
  DScy: "Ѕ",
  DZcy: "Џ",
  Dagger: "‡",
  Darr: "↡",
  Dashv: "⫤",
  Dcaron: "Ď",
  Dcy: "Д",
  Del: "∇",
  Delta: "Δ",
  Dfr: "𝔇",
  DiacriticalAcute: "´",
  DiacriticalDot: "˙",
  DiacriticalDoubleAcute: "˝",
  DiacriticalGrave: "`",
  DiacriticalTilde: "˜",
  Diamond: "⋄",
  DifferentialD: "ⅆ",
  Dopf: "𝔻",
  Dot: "¨",
  DotDot: "⃜",
  DotEqual: "≐",
  DoubleContourIntegral: "∯",
  DoubleDot: "¨",
  DoubleDownArrow: "⇓",
  DoubleLeftArrow: "⇐",
  DoubleLeftRightArrow: "⇔",
  DoubleLeftTee: "⫤",
  DoubleLongLeftArrow: "⟸",
  DoubleLongLeftRightArrow: "⟺",
  DoubleLongRightArrow: "⟹",
  DoubleRightArrow: "⇒",
  DoubleRightTee: "⊨",
  DoubleUpArrow: "⇑",
  DoubleUpDownArrow: "⇕",
  DoubleVerticalBar: "∥",
  DownArrow: "↓",
  DownArrowBar: "⤓",
  DownArrowUpArrow: "⇵",
  DownBreve: "̑",
  DownLeftRightVector: "⥐",
  DownLeftTeeVector: "⥞",
  DownLeftVector: "↽",
  DownLeftVectorBar: "⥖",
  DownRightTeeVector: "⥟",
  DownRightVector: "⇁",
  DownRightVectorBar: "⥗",
  DownTee: "⊤",
  DownTeeArrow: "↧",
  Downarrow: "⇓",
  Dscr: "𝒟",
  Dstrok: "Đ",
  ENG: "Ŋ",
  ETH: "Ð",
  Eacute: "É",
  Ecaron: "Ě",
  Ecirc: "Ê",
  Ecy: "Э",
  Edot: "Ė",
  Efr: "𝔈",
  Egrave: "È",
  Element: "∈",
  Emacr: "Ē",
  EmptySmallSquare: "◻",
  EmptyVerySmallSquare: "▫",
  Eogon: "Ę",
  Eopf: "𝔼",
  Epsilon: "Ε",
  Equal: "⩵",
  EqualTilde: "≂",
  Equilibrium: "⇌",
  Escr: "ℰ",
  Esim: "⩳",
  Eta: "Η",
  Euml: "Ë",
  Exists: "∃",
  ExponentialE: "ⅇ",
  Fcy: "Ф",
  Ffr: "𝔉",
  FilledSmallSquare: "◼",
  FilledVerySmallSquare: "▪",
  Fopf: "𝔽",
  ForAll: "∀",
  Fouriertrf: "ℱ",
  Fscr: "ℱ",
  GJcy: "Ѓ",
  GT: ">",
  Gamma: "Γ",
  Gammad: "Ϝ",
  Gbreve: "Ğ",
  Gcedil: "Ģ",
  Gcirc: "Ĝ",
  Gcy: "Г",
  Gdot: "Ġ",
  Gfr: "𝔊",
  Gg: "⋙",
  Gopf: "𝔾",
  GreaterEqual: "≥",
  GreaterEqualLess: "⋛",
  GreaterFullEqual: "≧",
  GreaterGreater: "⪢",
  GreaterLess: "≷",
  GreaterSlantEqual: "⩾",
  GreaterTilde: "≳",
  Gscr: "𝒢",
  Gt: "≫",
  HARDcy: "Ъ",
  Hacek: "ˇ",
  Hat: "^",
  Hcirc: "Ĥ",
  Hfr: "ℌ",
  HilbertSpace: "ℋ",
  Hopf: "ℍ",
  HorizontalLine: "─",
  Hscr: "ℋ",
  Hstrok: "Ħ",
  HumpDownHump: "≎",
  HumpEqual: "≏",
  IEcy: "Е",
  IJlig: "Ĳ",
  IOcy: "Ё",
  Iacute: "Í",
  Icirc: "Î",
  Icy: "И",
  Idot: "İ",
  Ifr: "ℑ",
  Igrave: "Ì",
  Im: "ℑ",
  Imacr: "Ī",
  ImaginaryI: "ⅈ",
  Implies: "⇒",
  Int: "∬",
  Integral: "∫",
  Intersection: "⋂",
  InvisibleComma: "⁣",
  InvisibleTimes: "⁢",
  Iogon: "Į",
  Iopf: "𝕀",
  Iota: "Ι",
  Iscr: "ℐ",
  Itilde: "Ĩ",
  Iukcy: "І",
  Iuml: "Ï",
  Jcirc: "Ĵ",
  Jcy: "Й",
  Jfr: "𝔍",
  Jopf: "𝕁",
  Jscr: "𝒥",
  Jsercy: "Ј",
  Jukcy: "Є",
  KHcy: "Х",
  KJcy: "Ќ",
  Kappa: "Κ",
  Kcedil: "Ķ",
  Kcy: "К",
  Kfr: "𝔎",
  Kopf: "𝕂",
  Kscr: "𝒦",
  LJcy: "Љ",
  LT: "<",
  Lacute: "Ĺ",
  Lambda: "Λ",
  Lang: "⟪",
  Laplacetrf: "ℒ",
  Larr: "↞",
  Lcaron: "Ľ",
  Lcedil: "Ļ",
  Lcy: "Л",
  LeftAngleBracket: "⟨",
  LeftArrow: "←",
  LeftArrowBar: "⇤",
  LeftArrowRightArrow: "⇆",
  LeftCeiling: "⌈",
  LeftDoubleBracket: "⟦",
  LeftDownTeeVector: "⥡",
  LeftDownVector: "⇃",
  LeftDownVectorBar: "⥙",
  LeftFloor: "⌊",
  LeftRightArrow: "↔",
  LeftRightVector: "⥎",
  LeftTee: "⊣",
  LeftTeeArrow: "↤",
  LeftTeeVector: "⥚",
  LeftTriangle: "⊲",
  LeftTriangleBar: "⧏",
  LeftTriangleEqual: "⊴",
  LeftUpDownVector: "⥑",
  LeftUpTeeVector: "⥠",
  LeftUpVector: "↿",
  LeftUpVectorBar: "⥘",
  LeftVector: "↼",
  LeftVectorBar: "⥒",
  Leftarrow: "⇐",
  Leftrightarrow: "⇔",
  LessEqualGreater: "⋚",
  LessFullEqual: "≦",
  LessGreater: "≶",
  LessLess: "⪡",
  LessSlantEqual: "⩽",
  LessTilde: "≲",
  Lfr: "𝔏",
  Ll: "⋘",
  Lleftarrow: "⇚",
  Lmidot: "Ŀ",
  LongLeftArrow: "⟵",
  LongLeftRightArrow: "⟷",
  LongRightArrow: "⟶",
  Longleftarrow: "⟸",
  Longleftrightarrow: "⟺",
  Longrightarrow: "⟹",
  Lopf: "𝕃",
  LowerLeftArrow: "↙",
  LowerRightArrow: "↘",
  Lscr: "ℒ",
  Lsh: "↰",
  Lstrok: "Ł",
  Lt: "≪",
  Map: "⤅",
  Mcy: "М",
  MediumSpace: " ",
  Mellintrf: "ℳ",
  Mfr: "𝔐",
  MinusPlus: "∓",
  Mopf: "𝕄",
  Mscr: "ℳ",
  Mu: "Μ",
  NJcy: "Њ",
  Nacute: "Ń",
  Ncaron: "Ň",
  Ncedil: "Ņ",
  Ncy: "Н",
  NegativeMediumSpace: "​",
  NegativeThickSpace: "​",
  NegativeThinSpace: "​",
  NegativeVeryThinSpace: "​",
  NestedGreaterGreater: "≫",
  NestedLessLess: "≪",
  NewLine: "\n",
  Nfr: "𝔑",
  NoBreak: "⁠",
  NonBreakingSpace: " ",
  Nopf: "ℕ",
  Not: "⫬",
  NotCongruent: "≢",
  NotCupCap: "≭",
  NotDoubleVerticalBar: "∦",
  NotElement: "∉",
  NotEqual: "≠",
  NotEqualTilde: "≂̸",
  NotExists: "∄",
  NotGreater: "≯",
  NotGreaterEqual: "≱",
  NotGreaterFullEqual: "≧̸",
  NotGreaterGreater: "≫̸",
  NotGreaterLess: "≹",
  NotGreaterSlantEqual: "⩾̸",
  NotGreaterTilde: "≵",
  NotHumpDownHump: "≎̸",
  NotHumpEqual: "≏̸",
  NotLeftTriangle: "⋪",
  NotLeftTriangleBar: "⧏̸",
  NotLeftTriangleEqual: "⋬",
  NotLess: "≮",
  NotLessEqual: "≰",
  NotLessGreater: "≸",
  NotLessLess: "≪̸",
  NotLessSlantEqual: "⩽̸",
  NotLessTilde: "≴",
  NotNestedGreaterGreater: "⪢̸",
  NotNestedLessLess: "⪡̸",
  NotPrecedes: "⊀",
  NotPrecedesEqual: "⪯̸",
  NotPrecedesSlantEqual: "⋠",
  NotReverseElement: "∌",
  NotRightTriangle: "⋫",
  NotRightTriangleBar: "⧐̸",
  NotRightTriangleEqual: "⋭",
  NotSquareSubset: "⊏̸",
  NotSquareSubsetEqual: "⋢",
  NotSquareSuperset: "⊐̸",
  NotSquareSupersetEqual: "⋣",
  NotSubset: "⊂⃒",
  NotSubsetEqual: "⊈",
  NotSucceeds: "⊁",
  NotSucceedsEqual: "⪰̸",
  NotSucceedsSlantEqual: "⋡",
  NotSucceedsTilde: "≿̸",
  NotSuperset: "⊃⃒",
  NotSupersetEqual: "⊉",
  NotTilde: "≁",
  NotTildeEqual: "≄",
  NotTildeFullEqual: "≇",
  NotTildeTilde: "≉",
  NotVerticalBar: "∤",
  Nscr: "𝒩",
  Ntilde: "Ñ",
  Nu: "Ν",
  OElig: "Œ",
  Oacute: "Ó",
  Ocirc: "Ô",
  Ocy: "О",
  Odblac: "Ő",
  Ofr: "𝔒",
  Ograve: "Ò",
  Omacr: "Ō",
  Omega: "Ω",
  Omicron: "Ο",
  Oopf: "𝕆",
  OpenCurlyDoubleQuote: "“",
  OpenCurlyQuote: "‘",
  Or: "⩔",
  Oscr: "𝒪",
  Oslash: "Ø",
  Otilde: "Õ",
  Otimes: "⨷",
  Ouml: "Ö",
  OverBar: "‾",
  OverBrace: "⏞",
  OverBracket: "⎴",
  OverParenthesis: "⏜",
  PartialD: "∂",
  Pcy: "П",
  Pfr: "𝔓",
  Phi: "Φ",
  Pi: "Π",
  PlusMinus: "±",
  Poincareplane: "ℌ",
  Popf: "ℙ",
  Pr: "⪻",
  Precedes: "≺",
  PrecedesEqual: "⪯",
  PrecedesSlantEqual: "≼",
  PrecedesTilde: "≾",
  Prime: "″",
  Product: "∏",
  Proportion: "∷",
  Proportional: "∝",
  Pscr: "𝒫",
  Psi: "Ψ",
  QUOT: '"',
  Qfr: "𝔔",
  Qopf: "ℚ",
  Qscr: "𝒬",
  RBarr: "⤐",
  REG: "®",
  Racute: "Ŕ",
  Rang: "⟫",
  Rarr: "↠",
  Rarrtl: "⤖",
  Rcaron: "Ř",
  Rcedil: "Ŗ",
  Rcy: "Р",
  Re: "ℜ",
  ReverseElement: "∋",
  ReverseEquilibrium: "⇋",
  ReverseUpEquilibrium: "⥯",
  Rfr: "ℜ",
  Rho: "Ρ",
  RightAngleBracket: "⟩",
  RightArrow: "→",
  RightArrowBar: "⇥",
  RightArrowLeftArrow: "⇄",
  RightCeiling: "⌉",
  RightDoubleBracket: "⟧",
  RightDownTeeVector: "⥝",
  RightDownVector: "⇂",
  RightDownVectorBar: "⥕",
  RightFloor: "⌋",
  RightTee: "⊢",
  RightTeeArrow: "↦",
  RightTeeVector: "⥛",
  RightTriangle: "⊳",
  RightTriangleBar: "⧐",
  RightTriangleEqual: "⊵",
  RightUpDownVector: "⥏",
  RightUpTeeVector: "⥜",
  RightUpVector: "↾",
  RightUpVectorBar: "⥔",
  RightVector: "⇀",
  RightVectorBar: "⥓",
  Rightarrow: "⇒",
  Ropf: "ℝ",
  RoundImplies: "⥰",
  Rrightarrow: "⇛",
  Rscr: "ℛ",
  Rsh: "↱",
  RuleDelayed: "⧴",
  SHCHcy: "Щ",
  SHcy: "Ш",
  SOFTcy: "Ь",
  Sacute: "Ś",
  Sc: "⪼",
  Scaron: "Š",
  Scedil: "Ş",
  Scirc: "Ŝ",
  Scy: "С",
  Sfr: "𝔖",
  ShortDownArrow: "↓",
  ShortLeftArrow: "←",
  ShortRightArrow: "→",
  ShortUpArrow: "↑",
  Sigma: "Σ",
  SmallCircle: "∘",
  Sopf: "𝕊",
  Sqrt: "√",
  Square: "□",
  SquareIntersection: "⊓",
  SquareSubset: "⊏",
  SquareSubsetEqual: "⊑",
  SquareSuperset: "⊐",
  SquareSupersetEqual: "⊒",
  SquareUnion: "⊔",
  Sscr: "𝒮",
  Star: "⋆",
  Sub: "⋐",
  Subset: "⋐",
  SubsetEqual: "⊆",
  Succeeds: "≻",
  SucceedsEqual: "⪰",
  SucceedsSlantEqual: "≽",
  SucceedsTilde: "≿",
  SuchThat: "∋",
  Sum: "∑",
  Sup: "⋑",
  Superset: "⊃",
  SupersetEqual: "⊇",
  Supset: "⋑",
  THORN: "Þ",
  TRADE: "™",
  TSHcy: "Ћ",
  TScy: "Ц",
  Tab: "	",
  Tau: "Τ",
  Tcaron: "Ť",
  Tcedil: "Ţ",
  Tcy: "Т",
  Tfr: "𝔗",
  Therefore: "∴",
  Theta: "Θ",
  ThickSpace: "  ",
  ThinSpace: " ",
  Tilde: "∼",
  TildeEqual: "≃",
  TildeFullEqual: "≅",
  TildeTilde: "≈",
  Topf: "𝕋",
  TripleDot: "⃛",
  Tscr: "𝒯",
  Tstrok: "Ŧ",
  Uacute: "Ú",
  Uarr: "↟",
  Uarrocir: "⥉",
  Ubrcy: "Ў",
  Ubreve: "Ŭ",
  Ucirc: "Û",
  Ucy: "У",
  Udblac: "Ű",
  Ufr: "𝔘",
  Ugrave: "Ù",
  Umacr: "Ū",
  UnderBar: "_",
  UnderBrace: "⏟",
  UnderBracket: "⎵",
  UnderParenthesis: "⏝",
  Union: "⋃",
  UnionPlus: "⊎",
  Uogon: "Ų",
  Uopf: "𝕌",
  UpArrow: "↑",
  UpArrowBar: "⤒",
  UpArrowDownArrow: "⇅",
  UpDownArrow: "↕",
  UpEquilibrium: "⥮",
  UpTee: "⊥",
  UpTeeArrow: "↥",
  Uparrow: "⇑",
  Updownarrow: "⇕",
  UpperLeftArrow: "↖",
  UpperRightArrow: "↗",
  Upsi: "ϒ",
  Upsilon: "Υ",
  Uring: "Ů",
  Uscr: "𝒰",
  Utilde: "Ũ",
  Uuml: "Ü",
  VDash: "⊫",
  Vbar: "⫫",
  Vcy: "В",
  Vdash: "⊩",
  Vdashl: "⫦",
  Vee: "⋁",
  Verbar: "‖",
  Vert: "‖",
  VerticalBar: "∣",
  VerticalLine: "|",
  VerticalSeparator: "❘",
  VerticalTilde: "≀",
  VeryThinSpace: " ",
  Vfr: "𝔙",
  Vopf: "𝕍",
  Vscr: "𝒱",
  Vvdash: "⊪",
  Wcirc: "Ŵ",
  Wedge: "⋀",
  Wfr: "𝔚",
  Wopf: "𝕎",
  Wscr: "𝒲",
  Xfr: "𝔛",
  Xi: "Ξ",
  Xopf: "𝕏",
  Xscr: "𝒳",
  YAcy: "Я",
  YIcy: "Ї",
  YUcy: "Ю",
  Yacute: "Ý",
  Ycirc: "Ŷ",
  Ycy: "Ы",
  Yfr: "𝔜",
  Yopf: "𝕐",
  Yscr: "𝒴",
  Yuml: "Ÿ",
  ZHcy: "Ж",
  Zacute: "Ź",
  Zcaron: "Ž",
  Zcy: "З",
  Zdot: "Ż",
  ZeroWidthSpace: "​",
  Zeta: "Ζ",
  Zfr: "ℨ",
  Zopf: "ℤ",
  Zscr: "𝒵",
  aacute: "á",
  abreve: "ă",
  ac: "∾",
  acE: "∾̳",
  acd: "∿",
  acirc: "â",
  acute: "´",
  acy: "а",
  aelig: "æ",
  af: "⁡",
  afr: "𝔞",
  agrave: "à",
  alefsym: "ℵ",
  aleph: "ℵ",
  alpha: "α",
  amacr: "ā",
  amalg: "⨿",
  amp: "&",
  and: "∧",
  andand: "⩕",
  andd: "⩜",
  andslope: "⩘",
  andv: "⩚",
  ang: "∠",
  ange: "⦤",
  angle: "∠",
  angmsd: "∡",
  angmsdaa: "⦨",
  angmsdab: "⦩",
  angmsdac: "⦪",
  angmsdad: "⦫",
  angmsdae: "⦬",
  angmsdaf: "⦭",
  angmsdag: "⦮",
  angmsdah: "⦯",
  angrt: "∟",
  angrtvb: "⊾",
  angrtvbd: "⦝",
  angsph: "∢",
  angst: "Å",
  angzarr: "⍼",
  aogon: "ą",
  aopf: "𝕒",
  ap: "≈",
  apE: "⩰",
  apacir: "⩯",
  ape: "≊",
  apid: "≋",
  apos: "'",
  approx: "≈",
  approxeq: "≊",
  aring: "å",
  ascr: "𝒶",
  ast: "*",
  asymp: "≈",
  asympeq: "≍",
  atilde: "ã",
  auml: "ä",
  awconint: "∳",
  awint: "⨑",
  bNot: "⫭",
  backcong: "≌",
  backepsilon: "϶",
  backprime: "‵",
  backsim: "∽",
  backsimeq: "⋍",
  barvee: "⊽",
  barwed: "⌅",
  barwedge: "⌅",
  bbrk: "⎵",
  bbrktbrk: "⎶",
  bcong: "≌",
  bcy: "б",
  bdquo: "„",
  becaus: "∵",
  because: "∵",
  bemptyv: "⦰",
  bepsi: "϶",
  bernou: "ℬ",
  beta: "β",
  beth: "ℶ",
  between: "≬",
  bfr: "𝔟",
  bigcap: "⋂",
  bigcirc: "◯",
  bigcup: "⋃",
  bigodot: "⨀",
  bigoplus: "⨁",
  bigotimes: "⨂",
  bigsqcup: "⨆",
  bigstar: "★",
  bigtriangledown: "▽",
  bigtriangleup: "△",
  biguplus: "⨄",
  bigvee: "⋁",
  bigwedge: "⋀",
  bkarow: "⤍",
  blacklozenge: "⧫",
  blacksquare: "▪",
  blacktriangle: "▴",
  blacktriangledown: "▾",
  blacktriangleleft: "◂",
  blacktriangleright: "▸",
  blank: "␣",
  blk12: "▒",
  blk14: "░",
  blk34: "▓",
  block: "█",
  bne: "=⃥",
  bnequiv: "≡⃥",
  bnot: "⌐",
  bopf: "𝕓",
  bot: "⊥",
  bottom: "⊥",
  bowtie: "⋈",
  boxDL: "╗",
  boxDR: "╔",
  boxDl: "╖",
  boxDr: "╓",
  boxH: "═",
  boxHD: "╦",
  boxHU: "╩",
  boxHd: "╤",
  boxHu: "╧",
  boxUL: "╝",
  boxUR: "╚",
  boxUl: "╜",
  boxUr: "╙",
  boxV: "║",
  boxVH: "╬",
  boxVL: "╣",
  boxVR: "╠",
  boxVh: "╫",
  boxVl: "╢",
  boxVr: "╟",
  boxbox: "⧉",
  boxdL: "╕",
  boxdR: "╒",
  boxdl: "┐",
  boxdr: "┌",
  boxh: "─",
  boxhD: "╥",
  boxhU: "╨",
  boxhd: "┬",
  boxhu: "┴",
  boxminus: "⊟",
  boxplus: "⊞",
  boxtimes: "⊠",
  boxuL: "╛",
  boxuR: "╘",
  boxul: "┘",
  boxur: "└",
  boxv: "│",
  boxvH: "╪",
  boxvL: "╡",
  boxvR: "╞",
  boxvh: "┼",
  boxvl: "┤",
  boxvr: "├",
  bprime: "‵",
  breve: "˘",
  brvbar: "¦",
  bscr: "𝒷",
  bsemi: "⁏",
  bsim: "∽",
  bsime: "⋍",
  bsol: "\\",
  bsolb: "⧅",
  bsolhsub: "⟈",
  bull: "•",
  bullet: "•",
  bump: "≎",
  bumpE: "⪮",
  bumpe: "≏",
  bumpeq: "≏",
  cacute: "ć",
  cap: "∩",
  capand: "⩄",
  capbrcup: "⩉",
  capcap: "⩋",
  capcup: "⩇",
  capdot: "⩀",
  caps: "∩︀",
  caret: "⁁",
  caron: "ˇ",
  ccaps: "⩍",
  ccaron: "č",
  ccedil: "ç",
  ccirc: "ĉ",
  ccups: "⩌",
  ccupssm: "⩐",
  cdot: "ċ",
  cedil: "¸",
  cemptyv: "⦲",
  cent: "¢",
  centerdot: "·",
  cfr: "𝔠",
  chcy: "ч",
  check: "✓",
  checkmark: "✓",
  chi: "χ",
  cir: "○",
  cirE: "⧃",
  circ: "ˆ",
  circeq: "≗",
  circlearrowleft: "↺",
  circlearrowright: "↻",
  circledR: "®",
  circledS: "Ⓢ",
  circledast: "⊛",
  circledcirc: "⊚",
  circleddash: "⊝",
  cire: "≗",
  cirfnint: "⨐",
  cirmid: "⫯",
  cirscir: "⧂",
  clubs: "♣",
  clubsuit: "♣",
  colon: ":",
  colone: "≔",
  coloneq: "≔",
  comma: ",",
  commat: "@",
  comp: "∁",
  compfn: "∘",
  complement: "∁",
  complexes: "ℂ",
  cong: "≅",
  congdot: "⩭",
  conint: "∮",
  copf: "𝕔",
  coprod: "∐",
  copy: "©",
  copysr: "℗",
  crarr: "↵",
  cross: "✗",
  cscr: "𝒸",
  csub: "⫏",
  csube: "⫑",
  csup: "⫐",
  csupe: "⫒",
  ctdot: "⋯",
  cudarrl: "⤸",
  cudarrr: "⤵",
  cuepr: "⋞",
  cuesc: "⋟",
  cularr: "↶",
  cularrp: "⤽",
  cup: "∪",
  cupbrcap: "⩈",
  cupcap: "⩆",
  cupcup: "⩊",
  cupdot: "⊍",
  cupor: "⩅",
  cups: "∪︀",
  curarr: "↷",
  curarrm: "⤼",
  curlyeqprec: "⋞",
  curlyeqsucc: "⋟",
  curlyvee: "⋎",
  curlywedge: "⋏",
  curren: "¤",
  curvearrowleft: "↶",
  curvearrowright: "↷",
  cuvee: "⋎",
  cuwed: "⋏",
  cwconint: "∲",
  cwint: "∱",
  cylcty: "⌭",
  dArr: "⇓",
  dHar: "⥥",
  dagger: "†",
  daleth: "ℸ",
  darr: "↓",
  dash: "‐",
  dashv: "⊣",
  dbkarow: "⤏",
  dblac: "˝",
  dcaron: "ď",
  dcy: "д",
  dd: "ⅆ",
  ddagger: "‡",
  ddarr: "⇊",
  ddotseq: "⩷",
  deg: "°",
  delta: "δ",
  demptyv: "⦱",
  dfisht: "⥿",
  dfr: "𝔡",
  dharl: "⇃",
  dharr: "⇂",
  diam: "⋄",
  diamond: "⋄",
  diamondsuit: "♦",
  diams: "♦",
  die: "¨",
  digamma: "ϝ",
  disin: "⋲",
  div: "÷",
  divide: "÷",
  divideontimes: "⋇",
  divonx: "⋇",
  djcy: "ђ",
  dlcorn: "⌞",
  dlcrop: "⌍",
  dollar: "$",
  dopf: "𝕕",
  dot: "˙",
  doteq: "≐",
  doteqdot: "≑",
  dotminus: "∸",
  dotplus: "∔",
  dotsquare: "⊡",
  doublebarwedge: "⌆",
  downarrow: "↓",
  downdownarrows: "⇊",
  downharpoonleft: "⇃",
  downharpoonright: "⇂",
  drbkarow: "⤐",
  drcorn: "⌟",
  drcrop: "⌌",
  dscr: "𝒹",
  dscy: "ѕ",
  dsol: "⧶",
  dstrok: "đ",
  dtdot: "⋱",
  dtri: "▿",
  dtrif: "▾",
  duarr: "⇵",
  duhar: "⥯",
  dwangle: "⦦",
  dzcy: "џ",
  dzigrarr: "⟿",
  eDDot: "⩷",
  eDot: "≑",
  eacute: "é",
  easter: "⩮",
  ecaron: "ě",
  ecir: "≖",
  ecirc: "ê",
  ecolon: "≕",
  ecy: "э",
  edot: "ė",
  ee: "ⅇ",
  efDot: "≒",
  efr: "𝔢",
  eg: "⪚",
  egrave: "è",
  egs: "⪖",
  egsdot: "⪘",
  el: "⪙",
  elinters: "⏧",
  ell: "ℓ",
  els: "⪕",
  elsdot: "⪗",
  emacr: "ē",
  empty: "∅",
  emptyset: "∅",
  emptyv: "∅",
  emsp13: " ",
  emsp14: " ",
  emsp: " ",
  eng: "ŋ",
  ensp: " ",
  eogon: "ę",
  eopf: "𝕖",
  epar: "⋕",
  eparsl: "⧣",
  eplus: "⩱",
  epsi: "ε",
  epsilon: "ε",
  epsiv: "ϵ",
  eqcirc: "≖",
  eqcolon: "≕",
  eqsim: "≂",
  eqslantgtr: "⪖",
  eqslantless: "⪕",
  equals: "=",
  equest: "≟",
  equiv: "≡",
  equivDD: "⩸",
  eqvparsl: "⧥",
  erDot: "≓",
  erarr: "⥱",
  escr: "ℯ",
  esdot: "≐",
  esim: "≂",
  eta: "η",
  eth: "ð",
  euml: "ë",
  euro: "€",
  excl: "!",
  exist: "∃",
  expectation: "ℰ",
  exponentiale: "ⅇ",
  fallingdotseq: "≒",
  fcy: "ф",
  female: "♀",
  ffilig: "ﬃ",
  fflig: "ﬀ",
  ffllig: "ﬄ",
  ffr: "𝔣",
  filig: "ﬁ",
  fjlig: "fj",
  flat: "♭",
  fllig: "ﬂ",
  fltns: "▱",
  fnof: "ƒ",
  fopf: "𝕗",
  forall: "∀",
  fork: "⋔",
  forkv: "⫙",
  fpartint: "⨍",
  frac12: "½",
  frac13: "⅓",
  frac14: "¼",
  frac15: "⅕",
  frac16: "⅙",
  frac18: "⅛",
  frac23: "⅔",
  frac25: "⅖",
  frac34: "¾",
  frac35: "⅗",
  frac38: "⅜",
  frac45: "⅘",
  frac56: "⅚",
  frac58: "⅝",
  frac78: "⅞",
  frasl: "⁄",
  frown: "⌢",
  fscr: "𝒻",
  gE: "≧",
  gEl: "⪌",
  gacute: "ǵ",
  gamma: "γ",
  gammad: "ϝ",
  gap: "⪆",
  gbreve: "ğ",
  gcirc: "ĝ",
  gcy: "г",
  gdot: "ġ",
  ge: "≥",
  gel: "⋛",
  geq: "≥",
  geqq: "≧",
  geqslant: "⩾",
  ges: "⩾",
  gescc: "⪩",
  gesdot: "⪀",
  gesdoto: "⪂",
  gesdotol: "⪄",
  gesl: "⋛︀",
  gesles: "⪔",
  gfr: "𝔤",
  gg: "≫",
  ggg: "⋙",
  gimel: "ℷ",
  gjcy: "ѓ",
  gl: "≷",
  glE: "⪒",
  gla: "⪥",
  glj: "⪤",
  gnE: "≩",
  gnap: "⪊",
  gnapprox: "⪊",
  gne: "⪈",
  gneq: "⪈",
  gneqq: "≩",
  gnsim: "⋧",
  gopf: "𝕘",
  grave: "`",
  gscr: "ℊ",
  gsim: "≳",
  gsime: "⪎",
  gsiml: "⪐",
  gt: ">",
  gtcc: "⪧",
  gtcir: "⩺",
  gtdot: "⋗",
  gtlPar: "⦕",
  gtquest: "⩼",
  gtrapprox: "⪆",
  gtrarr: "⥸",
  gtrdot: "⋗",
  gtreqless: "⋛",
  gtreqqless: "⪌",
  gtrless: "≷",
  gtrsim: "≳",
  gvertneqq: "≩︀",
  gvnE: "≩︀",
  hArr: "⇔",
  hairsp: " ",
  half: "½",
  hamilt: "ℋ",
  hardcy: "ъ",
  harr: "↔",
  harrcir: "⥈",
  harrw: "↭",
  hbar: "ℏ",
  hcirc: "ĥ",
  hearts: "♥",
  heartsuit: "♥",
  hellip: "…",
  hercon: "⊹",
  hfr: "𝔥",
  hksearow: "⤥",
  hkswarow: "⤦",
  hoarr: "⇿",
  homtht: "∻",
  hookleftarrow: "↩",
  hookrightarrow: "↪",
  hopf: "𝕙",
  horbar: "―",
  hscr: "𝒽",
  hslash: "ℏ",
  hstrok: "ħ",
  hybull: "⁃",
  hyphen: "‐",
  iacute: "í",
  ic: "⁣",
  icirc: "î",
  icy: "и",
  iecy: "е",
  iexcl: "¡",
  iff: "⇔",
  ifr: "𝔦",
  igrave: "ì",
  ii: "ⅈ",
  iiiint: "⨌",
  iiint: "∭",
  iinfin: "⧜",
  iiota: "℩",
  ijlig: "ĳ",
  imacr: "ī",
  image: "ℑ",
  imagline: "ℐ",
  imagpart: "ℑ",
  imath: "ı",
  imof: "⊷",
  imped: "Ƶ",
  in: "∈",
  incare: "℅",
  infin: "∞",
  infintie: "⧝",
  inodot: "ı",
  int: "∫",
  intcal: "⊺",
  integers: "ℤ",
  intercal: "⊺",
  intlarhk: "⨗",
  intprod: "⨼",
  iocy: "ё",
  iogon: "į",
  iopf: "𝕚",
  iota: "ι",
  iprod: "⨼",
  iquest: "¿",
  iscr: "𝒾",
  isin: "∈",
  isinE: "⋹",
  isindot: "⋵",
  isins: "⋴",
  isinsv: "⋳",
  isinv: "∈",
  it: "⁢",
  itilde: "ĩ",
  iukcy: "і",
  iuml: "ï",
  jcirc: "ĵ",
  jcy: "й",
  jfr: "𝔧",
  jmath: "ȷ",
  jopf: "𝕛",
  jscr: "𝒿",
  jsercy: "ј",
  jukcy: "є",
  kappa: "κ",
  kappav: "ϰ",
  kcedil: "ķ",
  kcy: "к",
  kfr: "𝔨",
  kgreen: "ĸ",
  khcy: "х",
  kjcy: "ќ",
  kopf: "𝕜",
  kscr: "𝓀",
  lAarr: "⇚",
  lArr: "⇐",
  lAtail: "⤛",
  lBarr: "⤎",
  lE: "≦",
  lEg: "⪋",
  lHar: "⥢",
  lacute: "ĺ",
  laemptyv: "⦴",
  lagran: "ℒ",
  lambda: "λ",
  lang: "⟨",
  langd: "⦑",
  langle: "⟨",
  lap: "⪅",
  laquo: "«",
  larr: "←",
  larrb: "⇤",
  larrbfs: "⤟",
  larrfs: "⤝",
  larrhk: "↩",
  larrlp: "↫",
  larrpl: "⤹",
  larrsim: "⥳",
  larrtl: "↢",
  lat: "⪫",
  latail: "⤙",
  late: "⪭",
  lates: "⪭︀",
  lbarr: "⤌",
  lbbrk: "❲",
  lbrace: "{",
  lbrack: "[",
  lbrke: "⦋",
  lbrksld: "⦏",
  lbrkslu: "⦍",
  lcaron: "ľ",
  lcedil: "ļ",
  lceil: "⌈",
  lcub: "{",
  lcy: "л",
  ldca: "⤶",
  ldquo: "“",
  ldquor: "„",
  ldrdhar: "⥧",
  ldrushar: "⥋",
  ldsh: "↲",
  le: "≤",
  leftarrow: "←",
  leftarrowtail: "↢",
  leftharpoondown: "↽",
  leftharpoonup: "↼",
  leftleftarrows: "⇇",
  leftrightarrow: "↔",
  leftrightarrows: "⇆",
  leftrightharpoons: "⇋",
  leftrightsquigarrow: "↭",
  leftthreetimes: "⋋",
  leg: "⋚",
  leq: "≤",
  leqq: "≦",
  leqslant: "⩽",
  les: "⩽",
  lescc: "⪨",
  lesdot: "⩿",
  lesdoto: "⪁",
  lesdotor: "⪃",
  lesg: "⋚︀",
  lesges: "⪓",
  lessapprox: "⪅",
  lessdot: "⋖",
  lesseqgtr: "⋚",
  lesseqqgtr: "⪋",
  lessgtr: "≶",
  lesssim: "≲",
  lfisht: "⥼",
  lfloor: "⌊",
  lfr: "𝔩",
  lg: "≶",
  lgE: "⪑",
  lhard: "↽",
  lharu: "↼",
  lharul: "⥪",
  lhblk: "▄",
  ljcy: "љ",
  ll: "≪",
  llarr: "⇇",
  llcorner: "⌞",
  llhard: "⥫",
  lltri: "◺",
  lmidot: "ŀ",
  lmoust: "⎰",
  lmoustache: "⎰",
  lnE: "≨",
  lnap: "⪉",
  lnapprox: "⪉",
  lne: "⪇",
  lneq: "⪇",
  lneqq: "≨",
  lnsim: "⋦",
  loang: "⟬",
  loarr: "⇽",
  lobrk: "⟦",
  longleftarrow: "⟵",
  longleftrightarrow: "⟷",
  longmapsto: "⟼",
  longrightarrow: "⟶",
  looparrowleft: "↫",
  looparrowright: "↬",
  lopar: "⦅",
  lopf: "𝕝",
  loplus: "⨭",
  lotimes: "⨴",
  lowast: "∗",
  lowbar: "_",
  loz: "◊",
  lozenge: "◊",
  lozf: "⧫",
  lpar: "(",
  lparlt: "⦓",
  lrarr: "⇆",
  lrcorner: "⌟",
  lrhar: "⇋",
  lrhard: "⥭",
  lrm: "‎",
  lrtri: "⊿",
  lsaquo: "‹",
  lscr: "𝓁",
  lsh: "↰",
  lsim: "≲",
  lsime: "⪍",
  lsimg: "⪏",
  lsqb: "[",
  lsquo: "‘",
  lsquor: "‚",
  lstrok: "ł",
  lt: "<",
  ltcc: "⪦",
  ltcir: "⩹",
  ltdot: "⋖",
  lthree: "⋋",
  ltimes: "⋉",
  ltlarr: "⥶",
  ltquest: "⩻",
  ltrPar: "⦖",
  ltri: "◃",
  ltrie: "⊴",
  ltrif: "◂",
  lurdshar: "⥊",
  luruhar: "⥦",
  lvertneqq: "≨︀",
  lvnE: "≨︀",
  mDDot: "∺",
  macr: "¯",
  male: "♂",
  malt: "✠",
  maltese: "✠",
  map: "↦",
  mapsto: "↦",
  mapstodown: "↧",
  mapstoleft: "↤",
  mapstoup: "↥",
  marker: "▮",
  mcomma: "⨩",
  mcy: "м",
  mdash: "—",
  measuredangle: "∡",
  mfr: "𝔪",
  mho: "℧",
  micro: "µ",
  mid: "∣",
  midast: "*",
  midcir: "⫰",
  middot: "·",
  minus: "−",
  minusb: "⊟",
  minusd: "∸",
  minusdu: "⨪",
  mlcp: "⫛",
  mldr: "…",
  mnplus: "∓",
  models: "⊧",
  mopf: "𝕞",
  mp: "∓",
  mscr: "𝓂",
  mstpos: "∾",
  mu: "μ",
  multimap: "⊸",
  mumap: "⊸",
  nGg: "⋙̸",
  nGt: "≫⃒",
  nGtv: "≫̸",
  nLeftarrow: "⇍",
  nLeftrightarrow: "⇎",
  nLl: "⋘̸",
  nLt: "≪⃒",
  nLtv: "≪̸",
  nRightarrow: "⇏",
  nVDash: "⊯",
  nVdash: "⊮",
  nabla: "∇",
  nacute: "ń",
  nang: "∠⃒",
  nap: "≉",
  napE: "⩰̸",
  napid: "≋̸",
  napos: "ŉ",
  napprox: "≉",
  natur: "♮",
  natural: "♮",
  naturals: "ℕ",
  nbsp: " ",
  nbump: "≎̸",
  nbumpe: "≏̸",
  ncap: "⩃",
  ncaron: "ň",
  ncedil: "ņ",
  ncong: "≇",
  ncongdot: "⩭̸",
  ncup: "⩂",
  ncy: "н",
  ndash: "–",
  ne: "≠",
  neArr: "⇗",
  nearhk: "⤤",
  nearr: "↗",
  nearrow: "↗",
  nedot: "≐̸",
  nequiv: "≢",
  nesear: "⤨",
  nesim: "≂̸",
  nexist: "∄",
  nexists: "∄",
  nfr: "𝔫",
  ngE: "≧̸",
  nge: "≱",
  ngeq: "≱",
  ngeqq: "≧̸",
  ngeqslant: "⩾̸",
  nges: "⩾̸",
  ngsim: "≵",
  ngt: "≯",
  ngtr: "≯",
  nhArr: "⇎",
  nharr: "↮",
  nhpar: "⫲",
  ni: "∋",
  nis: "⋼",
  nisd: "⋺",
  niv: "∋",
  njcy: "њ",
  nlArr: "⇍",
  nlE: "≦̸",
  nlarr: "↚",
  nldr: "‥",
  nle: "≰",
  nleftarrow: "↚",
  nleftrightarrow: "↮",
  nleq: "≰",
  nleqq: "≦̸",
  nleqslant: "⩽̸",
  nles: "⩽̸",
  nless: "≮",
  nlsim: "≴",
  nlt: "≮",
  nltri: "⋪",
  nltrie: "⋬",
  nmid: "∤",
  nopf: "𝕟",
  not: "¬",
  notin: "∉",
  notinE: "⋹̸",
  notindot: "⋵̸",
  notinva: "∉",
  notinvb: "⋷",
  notinvc: "⋶",
  notni: "∌",
  notniva: "∌",
  notnivb: "⋾",
  notnivc: "⋽",
  npar: "∦",
  nparallel: "∦",
  nparsl: "⫽⃥",
  npart: "∂̸",
  npolint: "⨔",
  npr: "⊀",
  nprcue: "⋠",
  npre: "⪯̸",
  nprec: "⊀",
  npreceq: "⪯̸",
  nrArr: "⇏",
  nrarr: "↛",
  nrarrc: "⤳̸",
  nrarrw: "↝̸",
  nrightarrow: "↛",
  nrtri: "⋫",
  nrtrie: "⋭",
  nsc: "⊁",
  nsccue: "⋡",
  nsce: "⪰̸",
  nscr: "𝓃",
  nshortmid: "∤",
  nshortparallel: "∦",
  nsim: "≁",
  nsime: "≄",
  nsimeq: "≄",
  nsmid: "∤",
  nspar: "∦",
  nsqsube: "⋢",
  nsqsupe: "⋣",
  nsub: "⊄",
  nsubE: "⫅̸",
  nsube: "⊈",
  nsubset: "⊂⃒",
  nsubseteq: "⊈",
  nsubseteqq: "⫅̸",
  nsucc: "⊁",
  nsucceq: "⪰̸",
  nsup: "⊅",
  nsupE: "⫆̸",
  nsupe: "⊉",
  nsupset: "⊃⃒",
  nsupseteq: "⊉",
  nsupseteqq: "⫆̸",
  ntgl: "≹",
  ntilde: "ñ",
  ntlg: "≸",
  ntriangleleft: "⋪",
  ntrianglelefteq: "⋬",
  ntriangleright: "⋫",
  ntrianglerighteq: "⋭",
  nu: "ν",
  num: "#",
  numero: "№",
  numsp: " ",
  nvDash: "⊭",
  nvHarr: "⤄",
  nvap: "≍⃒",
  nvdash: "⊬",
  nvge: "≥⃒",
  nvgt: ">⃒",
  nvinfin: "⧞",
  nvlArr: "⤂",
  nvle: "≤⃒",
  nvlt: "<⃒",
  nvltrie: "⊴⃒",
  nvrArr: "⤃",
  nvrtrie: "⊵⃒",
  nvsim: "∼⃒",
  nwArr: "⇖",
  nwarhk: "⤣",
  nwarr: "↖",
  nwarrow: "↖",
  nwnear: "⤧",
  oS: "Ⓢ",
  oacute: "ó",
  oast: "⊛",
  ocir: "⊚",
  ocirc: "ô",
  ocy: "о",
  odash: "⊝",
  odblac: "ő",
  odiv: "⨸",
  odot: "⊙",
  odsold: "⦼",
  oelig: "œ",
  ofcir: "⦿",
  ofr: "𝔬",
  ogon: "˛",
  ograve: "ò",
  ogt: "⧁",
  ohbar: "⦵",
  ohm: "Ω",
  oint: "∮",
  olarr: "↺",
  olcir: "⦾",
  olcross: "⦻",
  oline: "‾",
  olt: "⧀",
  omacr: "ō",
  omega: "ω",
  omicron: "ο",
  omid: "⦶",
  ominus: "⊖",
  oopf: "𝕠",
  opar: "⦷",
  operp: "⦹",
  oplus: "⊕",
  or: "∨",
  orarr: "↻",
  ord: "⩝",
  order: "ℴ",
  orderof: "ℴ",
  ordf: "ª",
  ordm: "º",
  origof: "⊶",
  oror: "⩖",
  orslope: "⩗",
  orv: "⩛",
  oscr: "ℴ",
  oslash: "ø",
  osol: "⊘",
  otilde: "õ",
  otimes: "⊗",
  otimesas: "⨶",
  ouml: "ö",
  ovbar: "⌽",
  par: "∥",
  para: "¶",
  parallel: "∥",
  parsim: "⫳",
  parsl: "⫽",
  part: "∂",
  pcy: "п",
  percnt: "%",
  period: ".",
  permil: "‰",
  perp: "⊥",
  pertenk: "‱",
  pfr: "𝔭",
  phi: "φ",
  phiv: "ϕ",
  phmmat: "ℳ",
  phone: "☎",
  pi: "π",
  pitchfork: "⋔",
  piv: "ϖ",
  planck: "ℏ",
  planckh: "ℎ",
  plankv: "ℏ",
  plus: "+",
  plusacir: "⨣",
  plusb: "⊞",
  pluscir: "⨢",
  plusdo: "∔",
  plusdu: "⨥",
  pluse: "⩲",
  plusmn: "±",
  plussim: "⨦",
  plustwo: "⨧",
  pm: "±",
  pointint: "⨕",
  popf: "𝕡",
  pound: "£",
  pr: "≺",
  prE: "⪳",
  prap: "⪷",
  prcue: "≼",
  pre: "⪯",
  prec: "≺",
  precapprox: "⪷",
  preccurlyeq: "≼",
  preceq: "⪯",
  precnapprox: "⪹",
  precneqq: "⪵",
  precnsim: "⋨",
  precsim: "≾",
  prime: "′",
  primes: "ℙ",
  prnE: "⪵",
  prnap: "⪹",
  prnsim: "⋨",
  prod: "∏",
  profalar: "⌮",
  profline: "⌒",
  profsurf: "⌓",
  prop: "∝",
  propto: "∝",
  prsim: "≾",
  prurel: "⊰",
  pscr: "𝓅",
  psi: "ψ",
  puncsp: " ",
  qfr: "𝔮",
  qint: "⨌",
  qopf: "𝕢",
  qprime: "⁗",
  qscr: "𝓆",
  quaternions: "ℍ",
  quatint: "⨖",
  quest: "?",
  questeq: "≟",
  quot: '"',
  rAarr: "⇛",
  rArr: "⇒",
  rAtail: "⤜",
  rBarr: "⤏",
  rHar: "⥤",
  race: "∽̱",
  racute: "ŕ",
  radic: "√",
  raemptyv: "⦳",
  rang: "⟩",
  rangd: "⦒",
  range: "⦥",
  rangle: "⟩",
  raquo: "»",
  rarr: "→",
  rarrap: "⥵",
  rarrb: "⇥",
  rarrbfs: "⤠",
  rarrc: "⤳",
  rarrfs: "⤞",
  rarrhk: "↪",
  rarrlp: "↬",
  rarrpl: "⥅",
  rarrsim: "⥴",
  rarrtl: "↣",
  rarrw: "↝",
  ratail: "⤚",
  ratio: "∶",
  rationals: "ℚ",
  rbarr: "⤍",
  rbbrk: "❳",
  rbrace: "}",
  rbrack: "]",
  rbrke: "⦌",
  rbrksld: "⦎",
  rbrkslu: "⦐",
  rcaron: "ř",
  rcedil: "ŗ",
  rceil: "⌉",
  rcub: "}",
  rcy: "р",
  rdca: "⤷",
  rdldhar: "⥩",
  rdquo: "”",
  rdquor: "”",
  rdsh: "↳",
  real: "ℜ",
  realine: "ℛ",
  realpart: "ℜ",
  reals: "ℝ",
  rect: "▭",
  reg: "®",
  rfisht: "⥽",
  rfloor: "⌋",
  rfr: "𝔯",
  rhard: "⇁",
  rharu: "⇀",
  rharul: "⥬",
  rho: "ρ",
  rhov: "ϱ",
  rightarrow: "→",
  rightarrowtail: "↣",
  rightharpoondown: "⇁",
  rightharpoonup: "⇀",
  rightleftarrows: "⇄",
  rightleftharpoons: "⇌",
  rightrightarrows: "⇉",
  rightsquigarrow: "↝",
  rightthreetimes: "⋌",
  ring: "˚",
  risingdotseq: "≓",
  rlarr: "⇄",
  rlhar: "⇌",
  rlm: "‏",
  rmoust: "⎱",
  rmoustache: "⎱",
  rnmid: "⫮",
  roang: "⟭",
  roarr: "⇾",
  robrk: "⟧",
  ropar: "⦆",
  ropf: "𝕣",
  roplus: "⨮",
  rotimes: "⨵",
  rpar: ")",
  rpargt: "⦔",
  rppolint: "⨒",
  rrarr: "⇉",
  rsaquo: "›",
  rscr: "𝓇",
  rsh: "↱",
  rsqb: "]",
  rsquo: "’",
  rsquor: "’",
  rthree: "⋌",
  rtimes: "⋊",
  rtri: "▹",
  rtrie: "⊵",
  rtrif: "▸",
  rtriltri: "⧎",
  ruluhar: "⥨",
  rx: "℞",
  sacute: "ś",
  sbquo: "‚",
  sc: "≻",
  scE: "⪴",
  scap: "⪸",
  scaron: "š",
  sccue: "≽",
  sce: "⪰",
  scedil: "ş",
  scirc: "ŝ",
  scnE: "⪶",
  scnap: "⪺",
  scnsim: "⋩",
  scpolint: "⨓",
  scsim: "≿",
  scy: "с",
  sdot: "⋅",
  sdotb: "⊡",
  sdote: "⩦",
  seArr: "⇘",
  searhk: "⤥",
  searr: "↘",
  searrow: "↘",
  sect: "§",
  semi: ";",
  seswar: "⤩",
  setminus: "∖",
  setmn: "∖",
  sext: "✶",
  sfr: "𝔰",
  sfrown: "⌢",
  sharp: "♯",
  shchcy: "щ",
  shcy: "ш",
  shortmid: "∣",
  shortparallel: "∥",
  shy: "­",
  sigma: "σ",
  sigmaf: "ς",
  sigmav: "ς",
  sim: "∼",
  simdot: "⩪",
  sime: "≃",
  simeq: "≃",
  simg: "⪞",
  simgE: "⪠",
  siml: "⪝",
  simlE: "⪟",
  simne: "≆",
  simplus: "⨤",
  simrarr: "⥲",
  slarr: "←",
  smallsetminus: "∖",
  smashp: "⨳",
  smeparsl: "⧤",
  smid: "∣",
  smile: "⌣",
  smt: "⪪",
  smte: "⪬",
  smtes: "⪬︀",
  softcy: "ь",
  sol: "/",
  solb: "⧄",
  solbar: "⌿",
  sopf: "𝕤",
  spades: "♠",
  spadesuit: "♠",
  spar: "∥",
  sqcap: "⊓",
  sqcaps: "⊓︀",
  sqcup: "⊔",
  sqcups: "⊔︀",
  sqsub: "⊏",
  sqsube: "⊑",
  sqsubset: "⊏",
  sqsubseteq: "⊑",
  sqsup: "⊐",
  sqsupe: "⊒",
  sqsupset: "⊐",
  sqsupseteq: "⊒",
  squ: "□",
  square: "□",
  squarf: "▪",
  squf: "▪",
  srarr: "→",
  sscr: "𝓈",
  ssetmn: "∖",
  ssmile: "⌣",
  sstarf: "⋆",
  star: "☆",
  starf: "★",
  straightepsilon: "ϵ",
  straightphi: "ϕ",
  strns: "¯",
  sub: "⊂",
  subE: "⫅",
  subdot: "⪽",
  sube: "⊆",
  subedot: "⫃",
  submult: "⫁",
  subnE: "⫋",
  subne: "⊊",
  subplus: "⪿",
  subrarr: "⥹",
  subset: "⊂",
  subseteq: "⊆",
  subseteqq: "⫅",
  subsetneq: "⊊",
  subsetneqq: "⫋",
  subsim: "⫇",
  subsub: "⫕",
  subsup: "⫓",
  succ: "≻",
  succapprox: "⪸",
  succcurlyeq: "≽",
  succeq: "⪰",
  succnapprox: "⪺",
  succneqq: "⪶",
  succnsim: "⋩",
  succsim: "≿",
  sum: "∑",
  sung: "♪",
  sup1: "¹",
  sup2: "²",
  sup3: "³",
  sup: "⊃",
  supE: "⫆",
  supdot: "⪾",
  supdsub: "⫘",
  supe: "⊇",
  supedot: "⫄",
  suphsol: "⟉",
  suphsub: "⫗",
  suplarr: "⥻",
  supmult: "⫂",
  supnE: "⫌",
  supne: "⊋",
  supplus: "⫀",
  supset: "⊃",
  supseteq: "⊇",
  supseteqq: "⫆",
  supsetneq: "⊋",
  supsetneqq: "⫌",
  supsim: "⫈",
  supsub: "⫔",
  supsup: "⫖",
  swArr: "⇙",
  swarhk: "⤦",
  swarr: "↙",
  swarrow: "↙",
  swnwar: "⤪",
  szlig: "ß",
  target: "⌖",
  tau: "τ",
  tbrk: "⎴",
  tcaron: "ť",
  tcedil: "ţ",
  tcy: "т",
  tdot: "⃛",
  telrec: "⌕",
  tfr: "𝔱",
  there4: "∴",
  therefore: "∴",
  theta: "θ",
  thetasym: "ϑ",
  thetav: "ϑ",
  thickapprox: "≈",
  thicksim: "∼",
  thinsp: " ",
  thkap: "≈",
  thksim: "∼",
  thorn: "þ",
  tilde: "˜",
  times: "×",
  timesb: "⊠",
  timesbar: "⨱",
  timesd: "⨰",
  tint: "∭",
  toea: "⤨",
  top: "⊤",
  topbot: "⌶",
  topcir: "⫱",
  topf: "𝕥",
  topfork: "⫚",
  tosa: "⤩",
  tprime: "‴",
  trade: "™",
  triangle: "▵",
  triangledown: "▿",
  triangleleft: "◃",
  trianglelefteq: "⊴",
  triangleq: "≜",
  triangleright: "▹",
  trianglerighteq: "⊵",
  tridot: "◬",
  trie: "≜",
  triminus: "⨺",
  triplus: "⨹",
  trisb: "⧍",
  tritime: "⨻",
  trpezium: "⏢",
  tscr: "𝓉",
  tscy: "ц",
  tshcy: "ћ",
  tstrok: "ŧ",
  twixt: "≬",
  twoheadleftarrow: "↞",
  twoheadrightarrow: "↠",
  uArr: "⇑",
  uHar: "⥣",
  uacute: "ú",
  uarr: "↑",
  ubrcy: "ў",
  ubreve: "ŭ",
  ucirc: "û",
  ucy: "у",
  udarr: "⇅",
  udblac: "ű",
  udhar: "⥮",
  ufisht: "⥾",
  ufr: "𝔲",
  ugrave: "ù",
  uharl: "↿",
  uharr: "↾",
  uhblk: "▀",
  ulcorn: "⌜",
  ulcorner: "⌜",
  ulcrop: "⌏",
  ultri: "◸",
  umacr: "ū",
  uml: "¨",
  uogon: "ų",
  uopf: "𝕦",
  uparrow: "↑",
  updownarrow: "↕",
  upharpoonleft: "↿",
  upharpoonright: "↾",
  uplus: "⊎",
  upsi: "υ",
  upsih: "ϒ",
  upsilon: "υ",
  upuparrows: "⇈",
  urcorn: "⌝",
  urcorner: "⌝",
  urcrop: "⌎",
  uring: "ů",
  urtri: "◹",
  uscr: "𝓊",
  utdot: "⋰",
  utilde: "ũ",
  utri: "▵",
  utrif: "▴",
  uuarr: "⇈",
  uuml: "ü",
  uwangle: "⦧",
  vArr: "⇕",
  vBar: "⫨",
  vBarv: "⫩",
  vDash: "⊨",
  vangrt: "⦜",
  varepsilon: "ϵ",
  varkappa: "ϰ",
  varnothing: "∅",
  varphi: "ϕ",
  varpi: "ϖ",
  varpropto: "∝",
  varr: "↕",
  varrho: "ϱ",
  varsigma: "ς",
  varsubsetneq: "⊊︀",
  varsubsetneqq: "⫋︀",
  varsupsetneq: "⊋︀",
  varsupsetneqq: "⫌︀",
  vartheta: "ϑ",
  vartriangleleft: "⊲",
  vartriangleright: "⊳",
  vcy: "в",
  vdash: "⊢",
  vee: "∨",
  veebar: "⊻",
  veeeq: "≚",
  vellip: "⋮",
  verbar: "|",
  vert: "|",
  vfr: "𝔳",
  vltri: "⊲",
  vnsub: "⊂⃒",
  vnsup: "⊃⃒",
  vopf: "𝕧",
  vprop: "∝",
  vrtri: "⊳",
  vscr: "𝓋",
  vsubnE: "⫋︀",
  vsubne: "⊊︀",
  vsupnE: "⫌︀",
  vsupne: "⊋︀",
  vzigzag: "⦚",
  wcirc: "ŵ",
  wedbar: "⩟",
  wedge: "∧",
  wedgeq: "≙",
  weierp: "℘",
  wfr: "𝔴",
  wopf: "𝕨",
  wp: "℘",
  wr: "≀",
  wreath: "≀",
  wscr: "𝓌",
  xcap: "⋂",
  xcirc: "◯",
  xcup: "⋃",
  xdtri: "▽",
  xfr: "𝔵",
  xhArr: "⟺",
  xharr: "⟷",
  xi: "ξ",
  xlArr: "⟸",
  xlarr: "⟵",
  xmap: "⟼",
  xnis: "⋻",
  xodot: "⨀",
  xopf: "𝕩",
  xoplus: "⨁",
  xotime: "⨂",
  xrArr: "⟹",
  xrarr: "⟶",
  xscr: "𝓍",
  xsqcup: "⨆",
  xuplus: "⨄",
  xutri: "△",
  xvee: "⋁",
  xwedge: "⋀",
  yacute: "ý",
  yacy: "я",
  ycirc: "ŷ",
  ycy: "ы",
  yen: "¥",
  yfr: "𝔶",
  yicy: "ї",
  yopf: "𝕪",
  yscr: "𝓎",
  yucy: "ю",
  yuml: "ÿ",
  zacute: "ź",
  zcaron: "ž",
  zcy: "з",
  zdot: "ż",
  zeetrf: "ℨ",
  zeta: "ζ",
  zfr: "𝔷",
  zhcy: "ж",
  zigrarr: "⇝",
  zopf: "𝕫",
  zscr: "𝓏",
  zwj: "‍",
  zwnj: "‌"
};

// node_modules/.pnpm/decode-named-character-reference@1.3.0/node_modules/decode-named-character-reference/index.js
var own = {}.hasOwnProperty;
function decodeNamedCharacterReference(value) {
  return own.call(characterEntities, value) ? characterEntities[value] : false;
}

// node_modules/.pnpm/micromark-util-chunked@2.0.1/node_modules/micromark-util-chunked/index.js
function splice(list4, start, remove, items) {
  const end = list4.length;
  let chunkStart = 0;
  let parameters;
  if (start < 0) {
    start = -start > end ? 0 : end + start;
  } else {
    start = start > end ? end : start;
  }
  remove = remove > 0 ? remove : 0;
  if (items.length < 1e4) {
    parameters = Array.from(items);
    parameters.unshift(start, remove);
    list4.splice(...parameters);
  } else {
    if (remove) list4.splice(start, remove);
    while (chunkStart < items.length) {
      parameters = items.slice(chunkStart, chunkStart + 1e4);
      parameters.unshift(start, 0);
      list4.splice(...parameters);
      chunkStart += 1e4;
      start += 1e4;
    }
  }
}
function push(list4, items) {
  if (list4.length > 0) {
    splice(list4, list4.length, 0, items);
    return list4;
  }
  return items;
}

// node_modules/.pnpm/micromark-util-combine-extensions@2.0.1/node_modules/micromark-util-combine-extensions/index.js
var hasOwnProperty = {}.hasOwnProperty;
function combineExtensions(extensions) {
  const all2 = {};
  let index2 = -1;
  while (++index2 < extensions.length) {
    syntaxExtension(all2, extensions[index2]);
  }
  return all2;
}
function syntaxExtension(all2, extension2) {
  let hook;
  for (hook in extension2) {
    const maybe = hasOwnProperty.call(all2, hook) ? all2[hook] : void 0;
    const left = maybe || (all2[hook] = {});
    const right = extension2[hook];
    let code4;
    if (right) {
      for (code4 in right) {
        if (!hasOwnProperty.call(left, code4)) left[code4] = [];
        const value = right[code4];
        constructs(
          // @ts-expect-error Looks like a list.
          left[code4],
          Array.isArray(value) ? value : value ? [value] : []
        );
      }
    }
  }
}
function constructs(existing, list4) {
  let index2 = -1;
  const before = [];
  while (++index2 < list4.length) {
    ;
    (list4[index2].add === "after" ? existing : before).push(list4[index2]);
  }
  splice(existing, 0, 0, before);
}

// node_modules/.pnpm/micromark-util-decode-numeric-character-reference@2.0.2/node_modules/micromark-util-decode-numeric-character-reference/index.js
function decodeNumericCharacterReference(value, base2) {
  const code4 = Number.parseInt(value, base2);
  if (
    // C0 except for HT, LF, FF, CR, space.
    code4 < 9 || code4 === 11 || code4 > 13 && code4 < 32 || // Control character (DEL) of C0, and C1 controls.
    code4 > 126 && code4 < 160 || // Lone high surrogates and low surrogates.
    code4 > 55295 && code4 < 57344 || // Noncharacters.
    code4 > 64975 && code4 < 65008 || /* eslint-disable no-bitwise */
    (code4 & 65535) === 65535 || (code4 & 65535) === 65534 || /* eslint-enable no-bitwise */
    // Out of range
    code4 > 1114111
  ) {
    return "�";
  }
  return String.fromCodePoint(code4);
}

// node_modules/.pnpm/micromark-util-normalize-identifier@2.0.1/node_modules/micromark-util-normalize-identifier/index.js
function normalizeIdentifier(value) {
  return value.replace(/[\t\n\r ]+/g, " ").replace(/^ | $/g, "").toLowerCase().toUpperCase();
}

// node_modules/.pnpm/micromark-util-character@2.1.1/node_modules/micromark-util-character/index.js
var asciiAlpha = regexCheck(/[A-Za-z]/);
var asciiAlphanumeric = regexCheck(/[\dA-Za-z]/);
var asciiAtext = regexCheck(/[#-'*+\--9=?A-Z^-~]/);
function asciiControl(code4) {
  return (
    // Special whitespace codes (which have negative values), C0 and Control
    // character DEL
    code4 !== null && (code4 < 32 || code4 === 127)
  );
}
var asciiDigit = regexCheck(/\d/);
var asciiHexDigit = regexCheck(/[\dA-Fa-f]/);
var asciiPunctuation = regexCheck(/[!-/:-@[-`{-~]/);
function markdownLineEnding(code4) {
  return code4 !== null && code4 < -2;
}
function markdownLineEndingOrSpace(code4) {
  return code4 !== null && (code4 < 0 || code4 === 32);
}
function markdownSpace(code4) {
  return code4 === -2 || code4 === -1 || code4 === 32;
}
var unicodePunctuation = regexCheck(/\p{P}|\p{S}/u);
var unicodeWhitespace = regexCheck(/\s/);
function regexCheck(regex) {
  return check2;
  function check2(code4) {
    return code4 !== null && code4 > -1 && regex.test(String.fromCharCode(code4));
  }
}

// node_modules/.pnpm/micromark-factory-space@2.1.0/node_modules/micromark-factory-space/index.js
function factorySpace(effects, ok2, type, max) {
  const limit = max ? max - 1 : Infinity;
  let size = 0;
  return start;
  function start(code4) {
    if (markdownSpace(code4)) {
      effects.enter(type);
      return prefix(code4);
    }
    return ok2(code4);
  }
  function prefix(code4) {
    if (markdownSpace(code4) && size++ < limit) {
      effects.consume(code4);
      return prefix;
    }
    effects.exit(type);
    return ok2(code4);
  }
}
function factorySpaceMinMax(effects, ok2, nok, type, min, max) {
  let size = 0;
  return start;
  function start(code4) {
    if (max > 0 && markdownSpace(code4)) {
      effects.enter(type);
      return prefix(code4);
    }
    return after(code4);
  }
  function prefix(code4) {
    if (markdownSpace(code4) && size < max) {
      effects.consume(code4);
      size++;
      return prefix;
    }
    effects.exit(type);
    return after(code4);
  }
  function after(code4) {
    return size >= min ? ok2(code4) : nok(code4);
  }
}

// node_modules/.pnpm/micromark@4.0.3/node_modules/micromark/lib/initialize/content.js
var content = {
  tokenize: initializeContent
};
function initializeContent(effects) {
  const contentStart = effects.attempt(this.parser.constructs.contentInitial, afterContentStartConstruct, paragraphInitial);
  let previous2;
  return contentStart;
  function afterContentStartConstruct(code4) {
    if (code4 === null) {
      effects.consume(code4);
      return;
    }
    effects.enter("lineEnding");
    effects.consume(code4);
    effects.exit("lineEnding");
    return factorySpace(effects, contentStart, "linePrefix");
  }
  function paragraphInitial(code4) {
    effects.enter("paragraph");
    return lineStart(code4);
  }
  function lineStart(code4) {
    const token = effects.enter("chunkText", {
      contentType: "text",
      previous: previous2
    });
    if (previous2) {
      previous2.next = token;
    }
    previous2 = token;
    return data(code4);
  }
  function data(code4) {
    if (code4 === null) {
      effects.exit("chunkText");
      effects.exit("paragraph");
      effects.consume(code4);
      return;
    }
    if (markdownLineEnding(code4)) {
      effects.consume(code4);
      effects.exit("chunkText");
      return lineStart;
    }
    effects.consume(code4);
    return data;
  }
}

// node_modules/.pnpm/micromark-util-edit-map@1.0.0/node_modules/micromark-util-edit-map/index.js
var EditMap = class {
  /**
   * Create a new edit map.
   *
   * @returns
   *   New instance.
   */
  constructor() {
    this.index = /* @__PURE__ */ new Map();
    this.map = [];
  }
  /**
   * Create an edit: a remove and/or add at a certain place.
   *
   * @param {number} index
   *   Index at which to apply the edit.
   * @param {number} remove
   *   Count of items to remove at the index.
   * @param {Array<Event>} add
   *   Items to add at the index.
   * @returns {undefined}
   *   Nothing.
   */
  add(index2, remove, add) {
    addImplementation(this, index2, remove, add, false);
  }
  /**
   * Create an edit: but insert `add` before existing additions, instead of
   * after them.
   *
   * @param {number} index
   *   Index at which to apply the edit.
   * @param {number} remove
   *   Count of items to remove at the index.
   * @param {Array<Event>} add
   *   Items to add at the index.
   * @returns {undefined}
   *   Nothing.
   */
  addBefore(index2, remove, add) {
    addImplementation(this, index2, remove, add, true);
  }
  /**
   * Done, change the events.
   *
   * @param {Array<Event>} events
   *   List of events to apply the edits to.
   * @returns {undefined}
   *   Nothing.
   */
  consume(events) {
    this.map.sort(function(a, b) {
      return a[0] - b[0];
    });
    if (this.map.length === 0) {
      return;
    }
    let index2 = this.map.length;
    const vecs = [];
    while (index2 > 0) {
      index2 -= 1;
      vecs.push(events.slice(this.map[index2][0] + this.map[index2][1]), this.map[index2][2]);
      events.length = this.map[index2][0];
    }
    vecs.push(events.slice());
    events.length = 0;
    let slice2 = vecs.pop();
    while (slice2) {
      for (const element of slice2) {
        events.push(element);
      }
      slice2 = vecs.pop();
    }
    this.map.length = 0;
    this.index.clear();
  }
};
function addImplementation(editMap, at, remove, add, before) {
  if (remove === 0 && add.length === 0) {
    return;
  }
  const existing = editMap.index.get(at);
  if (existing) {
    existing[1] += remove;
    if (before) {
      add.push(...existing[2]);
      existing[2] = add;
    } else {
      existing[2].push(...add);
    }
    return;
  }
  const change = [at, remove, add];
  editMap.map.push(change);
  editMap.index.set(at, change);
}

// node_modules/.pnpm/micromark@4.0.3/node_modules/micromark/lib/initialize/document.js
var document2 = {
  tokenize: initializeDocument
};
var containerConstruct = {
  tokenize: tokenizeContainer
};
function initializeDocument(effects) {
  const self = this;
  const stack = [];
  let continued = 0;
  let childFlow;
  let childToken;
  let lineStartOffset;
  return start;
  function start(code4) {
    if (continued < stack.length) {
      const item = stack[continued];
      self.containerState = item[1];
      return effects.attempt(item[0].continuation, documentContinue, checkNewContainers)(code4);
    }
    return checkNewContainers(code4);
  }
  function documentContinue(code4) {
    continued++;
    if (self.containerState._closeFlow) {
      self.containerState._closeFlow = void 0;
      if (childFlow) {
        closeFlow();
      }
      const indexBeforeExits = self.events.length;
      let indexBeforeFlow = indexBeforeExits;
      let point3;
      while (indexBeforeFlow--) {
        if (self.events[indexBeforeFlow][0] === "exit" && self.events[indexBeforeFlow][1].type === "chunkFlow") {
          point3 = self.events[indexBeforeFlow][1].end;
          break;
        }
      }
      exitContainers(continued);
      let index2 = indexBeforeExits;
      while (index2 < self.events.length) {
        self.events[index2][1].end = {
          ...point3
        };
        index2++;
      }
      const editMap = new EditMap();
      editMap.add(indexBeforeFlow + 1, 0, self.events.slice(indexBeforeExits));
      editMap.add(indexBeforeExits, index2 - indexBeforeExits, []);
      editMap.consume(self.events);
      return checkNewContainers(code4);
    }
    return start(code4);
  }
  function checkNewContainers(code4) {
    if (continued === stack.length) {
      if (!childFlow) {
        return documentContinued(code4);
      }
      if (childFlow.currentConstruct && childFlow.currentConstruct.concrete) {
        return flowStart(code4);
      }
      self.interrupt = Boolean(childFlow.currentConstruct && !childFlow._gfmTableDynamicInterruptHack);
    }
    self.containerState = {};
    return effects.check(containerConstruct, thereIsANewContainer, thereIsNoNewContainer)(code4);
  }
  function thereIsANewContainer(code4) {
    if (childFlow) {
      closeFlow();
    }
    exitContainers(continued);
    return documentContinued(code4);
  }
  function thereIsNoNewContainer(code4) {
    self.parser.lazy[self.now().line] = continued !== stack.length;
    lineStartOffset = self.now().offset;
    return flowStart(code4);
  }
  function documentContinued(code4) {
    self.containerState = {};
    return effects.attempt(containerConstruct, containerContinue, flowStart)(code4);
  }
  function containerContinue(code4) {
    continued++;
    stack.push([self.currentConstruct, self.containerState]);
    return documentContinued(code4);
  }
  function flowStart(code4) {
    if (code4 === null) {
      if (childFlow) {
        closeFlow();
      }
      exitContainers(0);
      effects.consume(code4);
      return;
    }
    childFlow = childFlow || self.parser.flow(self.now());
    effects.enter("chunkFlow", {
      _tokenizer: childFlow,
      contentType: "flow",
      previous: childToken
    });
    return flowContinue(code4);
  }
  function flowContinue(code4) {
    if (code4 === null) {
      writeToChild(effects.exit("chunkFlow"), true);
      exitContainers(0);
      effects.consume(code4);
      return;
    }
    if (markdownLineEnding(code4)) {
      effects.consume(code4);
      writeToChild(effects.exit("chunkFlow"));
      continued = 0;
      self.interrupt = void 0;
      return start;
    }
    effects.consume(code4);
    return flowContinue;
  }
  function writeToChild(token, endOfFile) {
    const stream = self.sliceStream(token);
    if (endOfFile) {
      stream.push(null);
    }
    token.previous = childToken;
    if (childToken) {
      childToken.next = token;
    }
    childToken = token;
    childFlow.defineSkip(token.start);
    childFlow.write(stream);
    if (self.parser.lazy[token.start.line]) {
      let index2 = childFlow.events.length;
      while (index2--) {
        if (
          // The token starts before the line ending…
          childFlow.events[index2][1].start.offset < lineStartOffset && // …and either is not ended yet…
          (!childFlow.events[index2][1].end || // …or ends after it.
          childFlow.events[index2][1].end.offset > lineStartOffset)
        ) {
          return;
        }
      }
      const indexBeforeExits = self.events.length;
      let indexBeforeFlow = indexBeforeExits;
      let seen;
      let point3;
      while (indexBeforeFlow--) {
        if (self.events[indexBeforeFlow][0] === "exit" && self.events[indexBeforeFlow][1].type === "chunkFlow") {
          if (seen) {
            point3 = self.events[indexBeforeFlow][1].end;
            break;
          }
          seen = true;
        }
      }
      exitContainers(continued);
      index2 = indexBeforeExits;
      while (index2 < self.events.length) {
        self.events[index2][1].end = {
          ...point3
        };
        index2++;
      }
      const editMap = new EditMap();
      editMap.add(indexBeforeFlow + 1, 0, self.events.slice(indexBeforeExits));
      editMap.add(indexBeforeExits, index2 - indexBeforeExits, []);
      editMap.consume(self.events);
    }
  }
  function exitContainers(size) {
    let index2 = stack.length;
    while (index2-- > size) {
      const entry = stack[index2];
      self.containerState = entry[1];
      entry[0].exit.call(self, effects);
    }
    stack.length = size;
  }
  function closeFlow() {
    childFlow.write([null]);
    childToken = void 0;
    childFlow = void 0;
    self.containerState._closeFlow = void 0;
  }
}
function tokenizeContainer(effects, ok2, nok) {
  return factorySpace(effects, effects.attempt(this.parser.constructs.document, ok2, nok), "linePrefix", this.parser.constructs.disable.null.includes("codeIndented") ? void 0 : 4);
}

// node_modules/.pnpm/micromark-util-classify-character@2.0.1/node_modules/micromark-util-classify-character/index.js
function classifyCharacter(code4) {
  if (code4 === null || markdownLineEndingOrSpace(code4) || unicodeWhitespace(code4)) {
    return 1;
  }
  if (unicodePunctuation(code4)) {
    return 2;
  }
}

// node_modules/.pnpm/micromark-util-resolve-all@2.0.1/node_modules/micromark-util-resolve-all/index.js
function resolveAll(constructs2, events, context) {
  const called = [];
  let index2 = -1;
  while (++index2 < constructs2.length) {
    const resolve = constructs2[index2].resolveAll;
    if (resolve && !called.includes(resolve)) {
      events = resolve(events, context);
      called.push(resolve);
    }
  }
  return events;
}

// node_modules/.pnpm/micromark-core-commonmark@2.0.4/node_modules/micromark-core-commonmark/lib/attention.js
var attention = {
  name: "attention",
  resolveAll: resolveAllAttention,
  tokenize: tokenizeAttention
};
function resolveAllAttention(events, context) {
  let index2 = -1;
  let nextEvents;
  while (++index2 < events.length) {
    if (events[index2][0] === "enter" && events[index2][1].type === "attentionSequence" && events[index2][1]._close) {
      let open = index2;
      while (open--) {
        if (events[open][0] === "exit" && events[open][1].type === "attentionSequence" && events[open][1]._open && // If the markers are the same:
        context.sliceSerialize(events[open][1]).charCodeAt(0) === context.sliceSerialize(events[index2][1]).charCodeAt(0)) {
          if ((events[open][1]._close || events[index2][1]._open) && (events[index2][1].end.offset - events[index2][1].start.offset) % 3 && !((events[open][1].end.offset - events[open][1].start.offset + events[index2][1].end.offset - events[index2][1].start.offset) % 3)) {
            continue;
          }
          const use = events[open][1].end.offset - events[open][1].start.offset > 1 && events[index2][1].end.offset - events[index2][1].start.offset > 1 ? 2 : 1;
          const start = {
            ...events[open][1].end
          };
          const end = {
            ...events[index2][1].start
          };
          movePoint(start, -use);
          movePoint(end, use);
          const openingSequence = {
            type: use > 1 ? "strongSequence" : "emphasisSequence",
            start,
            end: {
              ...events[open][1].end
            }
          };
          const closingSequence = {
            type: use > 1 ? "strongSequence" : "emphasisSequence",
            start: {
              ...events[index2][1].start
            },
            end
          };
          const text4 = {
            type: use > 1 ? "strongText" : "emphasisText",
            start: {
              ...events[open][1].end
            },
            end: {
              ...events[index2][1].start
            }
          };
          const group = {
            type: use > 1 ? "strong" : "emphasis",
            start: {
              ...openingSequence.start
            },
            end: {
              ...closingSequence.end
            }
          };
          events[open][1].end = {
            ...openingSequence.start
          };
          events[index2][1].start = {
            ...closingSequence.end
          };
          nextEvents = [];
          if (events[open][1].end.offset - events[open][1].start.offset) {
            nextEvents = push(nextEvents, [["enter", events[open][1], context], ["exit", events[open][1], context]]);
          }
          nextEvents = push(nextEvents, [["enter", group, context], ["enter", openingSequence, context], ["exit", openingSequence, context], ["enter", text4, context]]);
          nextEvents = push(nextEvents, resolveAll(context.parser.constructs.insideSpan.null, events.slice(open + 1, index2), context));
          nextEvents = push(nextEvents, [["exit", text4, context], ["enter", closingSequence, context], ["exit", closingSequence, context], ["exit", group, context]]);
          let offset = 0;
          if (events[index2][1].end.offset - events[index2][1].start.offset) {
            offset = 2;
            nextEvents = push(nextEvents, [["enter", events[index2][1], context], ["exit", events[index2][1], context]]);
          }
          splice(events, open - 1, index2 - open + 3, nextEvents);
          index2 = open + nextEvents.length - offset - 2;
          break;
        }
      }
    }
  }
  index2 = -1;
  while (++index2 < events.length) {
    if (events[index2][1].type === "attentionSequence") {
      events[index2][1].type = "data";
    }
  }
  return events;
}
function tokenizeAttention(effects, ok2) {
  const attentionMarkers2 = this.parser.constructs.attentionMarkers.null;
  const previous2 = this.previous;
  const before = classifyCharacter(previous2);
  let marker;
  return start;
  function start(code4) {
    marker = code4;
    effects.enter("attentionSequence");
    return inside(code4);
  }
  function inside(code4) {
    if (code4 === marker) {
      effects.consume(code4);
      return inside;
    }
    const token = effects.exit("attentionSequence");
    const after = classifyCharacter(code4);
    const open = !after || after === 2 && before || attentionMarkers2.includes(code4) && code4 !== 42 && code4 !== 95;
    const close2 = !before || before === 2 && after || attentionMarkers2.includes(previous2) && previous2 !== 42 && previous2 !== 95;
    token._open = Boolean(marker === 42 ? open : open && (before || !close2));
    token._close = Boolean(marker === 42 ? close2 : close2 && (after || !open));
    return ok2(code4);
  }
}
function movePoint(point3, offset) {
  point3.column += offset;
  point3.offset += offset;
  point3._bufferIndex += offset;
}

// node_modules/.pnpm/micromark-core-commonmark@2.0.4/node_modules/micromark-core-commonmark/lib/autolink.js
var autolink = {
  name: "autolink",
  tokenize: tokenizeAutolink
};
function tokenizeAutolink(effects, ok2, nok) {
  let size = 0;
  return start;
  function start(code4) {
    effects.enter("autolink");
    effects.enter("autolinkMarker");
    effects.consume(code4);
    effects.exit("autolinkMarker");
    effects.enter("autolinkProtocol");
    return open;
  }
  function open(code4) {
    if (asciiAlpha(code4)) {
      effects.consume(code4);
      return schemeOrEmailAtext;
    }
    if (code4 === 64) {
      return nok(code4);
    }
    return emailAtext(code4);
  }
  function schemeOrEmailAtext(code4) {
    if (code4 === 43 || code4 === 45 || code4 === 46 || asciiAlphanumeric(code4)) {
      size = 1;
      return schemeInsideOrEmailAtext(code4);
    }
    return emailAtext(code4);
  }
  function schemeInsideOrEmailAtext(code4) {
    if (code4 === 58) {
      effects.consume(code4);
      size = 0;
      return urlInside;
    }
    if ((code4 === 43 || code4 === 45 || code4 === 46 || asciiAlphanumeric(code4)) && size++ < 32) {
      effects.consume(code4);
      return schemeInsideOrEmailAtext;
    }
    size = 0;
    return emailAtext(code4);
  }
  function urlInside(code4) {
    if (code4 === 62) {
      effects.exit("autolinkProtocol");
      effects.enter("autolinkMarker");
      effects.consume(code4);
      effects.exit("autolinkMarker");
      effects.exit("autolink");
      return ok2;
    }
    if (code4 === null || code4 === 32 || code4 === 60 || asciiControl(code4)) {
      return nok(code4);
    }
    effects.consume(code4);
    return urlInside;
  }
  function emailAtext(code4) {
    if (code4 === 64) {
      effects.consume(code4);
      return emailAtSignOrDot;
    }
    if (asciiAtext(code4)) {
      effects.consume(code4);
      return emailAtext;
    }
    return nok(code4);
  }
  function emailAtSignOrDot(code4) {
    return asciiAlphanumeric(code4) ? emailLabel(code4) : nok(code4);
  }
  function emailLabel(code4) {
    if (code4 === 46) {
      effects.consume(code4);
      size = 0;
      return emailAtSignOrDot;
    }
    if (code4 === 62) {
      effects.exit("autolinkProtocol").type = "autolinkEmail";
      effects.enter("autolinkMarker");
      effects.consume(code4);
      effects.exit("autolinkMarker");
      effects.exit("autolink");
      return ok2;
    }
    return emailValue(code4);
  }
  function emailValue(code4) {
    if ((code4 === 45 || asciiAlphanumeric(code4)) && size++ < 63) {
      const next = code4 === 45 ? emailValue : emailLabel;
      effects.consume(code4);
      return next;
    }
    return nok(code4);
  }
}

// node_modules/.pnpm/micromark-core-commonmark@2.0.4/node_modules/micromark-core-commonmark/lib/blank-line.js
var blankLine = {
  partial: true,
  tokenize: tokenizeBlankLine
};
function tokenizeBlankLine(effects, ok2, nok) {
  return start;
  function start(code4) {
    return markdownSpace(code4) ? factorySpace(effects, after, "linePrefix")(code4) : after(code4);
  }
  function after(code4) {
    return code4 === null || markdownLineEnding(code4) ? ok2(code4) : nok(code4);
  }
}

// node_modules/.pnpm/micromark-core-commonmark@2.0.4/node_modules/micromark-core-commonmark/lib/block-quote.js
var blockQuote = {
  continuation: {
    tokenize: tokenizeBlockQuoteContinuation
  },
  exit,
  name: "blockQuote",
  tokenize: tokenizeBlockQuoteStart
};
function tokenizeBlockQuoteStart(effects, ok2, nok) {
  const self = this;
  return start;
  function start(code4) {
    if (code4 === 62) {
      const state = self.containerState;
      if (!state.open) {
        effects.enter("blockQuote", {
          _container: true
        });
        state.open = true;
      }
      effects.enter("blockQuotePrefix");
      effects.enter("blockQuoteMarker");
      effects.consume(code4);
      effects.exit("blockQuoteMarker");
      return after;
    }
    return nok(code4);
  }
  function after(code4) {
    if (markdownSpace(code4)) {
      effects.enter("blockQuotePrefixWhitespace");
      effects.consume(code4);
      effects.exit("blockQuotePrefixWhitespace");
      effects.exit("blockQuotePrefix");
      return ok2;
    }
    effects.exit("blockQuotePrefix");
    return ok2(code4);
  }
}
function tokenizeBlockQuoteContinuation(effects, ok2, nok) {
  const self = this;
  return contStart;
  function contStart(code4) {
    if (markdownSpace(code4)) {
      return factorySpace(effects, contBefore, "linePrefix", self.parser.constructs.disable.null.includes("codeIndented") ? void 0 : 4)(code4);
    }
    return contBefore(code4);
  }
  function contBefore(code4) {
    return effects.attempt(blockQuote, ok2, nok)(code4);
  }
}
function exit(effects) {
  effects.exit("blockQuote");
}

// node_modules/.pnpm/micromark-core-commonmark@2.0.4/node_modules/micromark-core-commonmark/lib/character-escape.js
var characterEscape = {
  name: "characterEscape",
  tokenize: tokenizeCharacterEscape
};
function tokenizeCharacterEscape(effects, ok2, nok) {
  return start;
  function start(code4) {
    effects.enter("characterEscape");
    effects.enter("escapeMarker");
    effects.consume(code4);
    effects.exit("escapeMarker");
    return inside;
  }
  function inside(code4) {
    if (asciiPunctuation(code4)) {
      effects.enter("characterEscapeValue");
      effects.consume(code4);
      effects.exit("characterEscapeValue");
      effects.exit("characterEscape");
      return ok2;
    }
    return nok(code4);
  }
}

// node_modules/.pnpm/micromark-core-commonmark@2.0.4/node_modules/micromark-core-commonmark/lib/character-reference.js
var characterReference = {
  name: "characterReference",
  tokenize: tokenizeCharacterReference
};
function tokenizeCharacterReference(effects, ok2, nok) {
  const self = this;
  let size = 0;
  let max;
  let test;
  return start;
  function start(code4) {
    effects.enter("characterReference");
    effects.enter("characterReferenceMarker");
    effects.consume(code4);
    effects.exit("characterReferenceMarker");
    return open;
  }
  function open(code4) {
    if (code4 === 35) {
      effects.enter("characterReferenceMarkerNumeric");
      effects.consume(code4);
      effects.exit("characterReferenceMarkerNumeric");
      return numeric;
    }
    effects.enter("characterReferenceValue");
    max = 31;
    test = asciiAlphanumeric;
    return value(code4);
  }
  function numeric(code4) {
    if (code4 === 88 || code4 === 120) {
      effects.enter("characterReferenceMarkerHexadecimal");
      effects.consume(code4);
      effects.exit("characterReferenceMarkerHexadecimal");
      effects.enter("characterReferenceValue");
      max = 6;
      test = asciiHexDigit;
      return value;
    }
    effects.enter("characterReferenceValue");
    max = 7;
    test = asciiDigit;
    return value(code4);
  }
  function value(code4) {
    if (code4 === 59 && size) {
      const token = effects.exit("characterReferenceValue");
      if (test === asciiAlphanumeric && !decodeNamedCharacterReference(self.sliceSerialize(token))) {
        return nok(code4);
      }
      effects.enter("characterReferenceMarker");
      effects.consume(code4);
      effects.exit("characterReferenceMarker");
      effects.exit("characterReference");
      return ok2;
    }
    if (test(code4) && size++ < max) {
      effects.consume(code4);
      return value;
    }
    return nok(code4);
  }
}

// node_modules/.pnpm/micromark-core-commonmark@2.0.4/node_modules/micromark-core-commonmark/lib/partial-non-lazy-continuation.js
var nonLazyContinuation = {
  partial: true,
  tokenize: tokenizeNonLazyContinuation
};
function tokenizeNonLazyContinuation(effects, ok2, nok) {
  const self = this;
  return start;
  function start(code4) {
    if (code4 === null) {
      return nok(code4);
    }
    effects.enter("lineEnding");
    effects.consume(code4);
    effects.exit("lineEnding");
    return after;
  }
  function after(code4) {
    return self.parser.lazy[self.now().line] ? nok(code4) : ok2(code4);
  }
}

// node_modules/.pnpm/micromark-core-commonmark@2.0.4/node_modules/micromark-core-commonmark/lib/code-fenced.js
var codeFenced = {
  concrete: true,
  name: "codeFenced",
  tokenize: tokenizeCodeFenced
};
function tokenizeCodeFenced(effects, ok2, nok) {
  const self = this;
  const closeStart = {
    partial: true,
    tokenize: tokenizeCloseStart
  };
  let initialPrefix = 0;
  let sizeOpen = 0;
  let marker;
  return start;
  function start(code4) {
    return beforeSequenceOpen(code4);
  }
  function beforeSequenceOpen(code4) {
    const tail = self.events[self.events.length - 1];
    initialPrefix = tail && tail[1].type === "linePrefix" ? tail[2].sliceSerialize(tail[1], true).length : 0;
    marker = code4;
    effects.enter("codeFenced");
    effects.enter("codeFencedFence");
    effects.enter("codeFencedFenceSequence");
    return sequenceOpen(code4);
  }
  function sequenceOpen(code4) {
    if (code4 === marker) {
      sizeOpen++;
      effects.consume(code4);
      return sequenceOpen;
    }
    if (sizeOpen < 3) {
      return nok(code4);
    }
    effects.exit("codeFencedFenceSequence");
    return markdownSpace(code4) ? factorySpace(effects, infoBefore, "whitespace")(code4) : infoBefore(code4);
  }
  function infoBefore(code4) {
    if (code4 === null || markdownLineEnding(code4)) {
      effects.exit("codeFencedFence");
      return self.interrupt ? ok2(code4) : effects.check(nonLazyContinuation, atNonLazyBreak, after)(code4);
    }
    effects.enter("codeFencedFenceInfo");
    effects.enter("chunkString", {
      contentType: "string"
    });
    return info(code4);
  }
  function info(code4) {
    if (code4 === null || markdownLineEnding(code4)) {
      effects.exit("chunkString");
      effects.exit("codeFencedFenceInfo");
      return infoBefore(code4);
    }
    if (markdownSpace(code4)) {
      effects.exit("chunkString");
      effects.exit("codeFencedFenceInfo");
      return factorySpace(effects, metaBefore, "whitespace")(code4);
    }
    if (code4 === 96 && code4 === marker) {
      return nok(code4);
    }
    effects.consume(code4);
    return info;
  }
  function metaBefore(code4) {
    if (code4 === null || markdownLineEnding(code4)) {
      return infoBefore(code4);
    }
    effects.enter("codeFencedFenceMeta");
    effects.enter("chunkString", {
      contentType: "string"
    });
    return meta(code4);
  }
  function meta(code4) {
    if (code4 === null || markdownLineEnding(code4)) {
      effects.exit("chunkString");
      effects.exit("codeFencedFenceMeta");
      return infoBefore(code4);
    }
    if (code4 === 96 && code4 === marker) {
      return nok(code4);
    }
    effects.consume(code4);
    return meta;
  }
  function atNonLazyBreak(code4) {
    return effects.attempt(closeStart, after, contentBefore)(code4);
  }
  function contentBefore(code4) {
    effects.enter("lineEnding");
    effects.consume(code4);
    effects.exit("lineEnding");
    return contentStart;
  }
  function contentStart(code4) {
    return initialPrefix > 0 && markdownSpace(code4) ? factorySpace(effects, beforeContentChunk, "linePrefix", initialPrefix + 1)(code4) : beforeContentChunk(code4);
  }
  function beforeContentChunk(code4) {
    if (code4 === null || markdownLineEnding(code4)) {
      return effects.check(nonLazyContinuation, atNonLazyBreak, after)(code4);
    }
    effects.enter("codeFlowValue");
    return contentChunk(code4);
  }
  function contentChunk(code4) {
    if (code4 === null || markdownLineEnding(code4)) {
      effects.exit("codeFlowValue");
      return beforeContentChunk(code4);
    }
    effects.consume(code4);
    return contentChunk;
  }
  function after(code4) {
    effects.exit("codeFenced");
    return ok2(code4);
  }
  function tokenizeCloseStart(effects2, ok3, nok2) {
    let size = 0;
    return startBefore;
    function startBefore(code4) {
      effects2.enter("lineEnding");
      effects2.consume(code4);
      effects2.exit("lineEnding");
      return start2;
    }
    function start2(code4) {
      effects2.enter("codeFencedFence");
      return markdownSpace(code4) ? factorySpace(effects2, beforeSequenceClose, "linePrefix", self.parser.constructs.disable.null.includes("codeIndented") ? void 0 : 4)(code4) : beforeSequenceClose(code4);
    }
    function beforeSequenceClose(code4) {
      if (code4 === marker) {
        effects2.enter("codeFencedFenceSequence");
        return sequenceClose(code4);
      }
      return nok2(code4);
    }
    function sequenceClose(code4) {
      if (code4 === marker) {
        size++;
        effects2.consume(code4);
        return sequenceClose;
      }
      if (size >= sizeOpen) {
        effects2.exit("codeFencedFenceSequence");
        return markdownSpace(code4) ? factorySpace(effects2, sequenceCloseAfter, "whitespace")(code4) : sequenceCloseAfter(code4);
      }
      return nok2(code4);
    }
    function sequenceCloseAfter(code4) {
      if (code4 === null || markdownLineEnding(code4)) {
        effects2.exit("codeFencedFence");
        return ok3(code4);
      }
      return nok2(code4);
    }
  }
}

// node_modules/.pnpm/micromark-core-commonmark@2.0.4/node_modules/micromark-core-commonmark/lib/code-indented.js
var codeIndented = {
  name: "codeIndented",
  tokenize: tokenizeCodeIndented
};
var furtherStart = {
  partial: true,
  tokenize: tokenizeFurtherStart
};
function tokenizeCodeIndented(effects, ok2, nok) {
  return start;
  function start(code4) {
    effects.enter("codeIndented");
    return factorySpaceMinMax(effects, atBreak, nok, "linePrefix", 4, 4)(code4);
  }
  function atBreak(code4) {
    if (code4 === null) {
      return after(code4);
    }
    if (markdownLineEnding(code4)) {
      return effects.attempt(furtherStart, atBreak, after)(code4);
    }
    effects.enter("codeFlowValue");
    return inside(code4);
  }
  function inside(code4) {
    if (code4 === null || markdownLineEnding(code4)) {
      effects.exit("codeFlowValue");
      return atBreak(code4);
    }
    effects.consume(code4);
    return inside;
  }
  function after(code4) {
    effects.exit("codeIndented");
    return ok2(code4);
  }
}
function tokenizeFurtherStart(effects, ok2, nok) {
  const self = this;
  return furtherStart2;
  function furtherStart2(code4) {
    if (self.parser.lazy[self.now().line]) {
      return nok(code4);
    }
    if (markdownLineEnding(code4)) {
      effects.enter("lineEnding");
      effects.consume(code4);
      effects.exit("lineEnding");
      return furtherStart2;
    }
    return factorySpaceMinMax(effects, ok2, onNotEnoughPrefix, "linePrefix", 4, 4)(code4);
  }
  function onNotEnoughPrefix(code4) {
    return markdownLineEnding(code4) ? furtherStart2(code4) : nok(code4);
  }
}

// node_modules/.pnpm/micromark-core-commonmark@2.0.4/node_modules/micromark-core-commonmark/lib/code-text.js
var codeText = {
  name: "codeText",
  previous,
  resolve: resolveCodeText,
  tokenize: tokenizeCodeText
};
function resolveCodeText(events) {
  let tailExitIndex = events.length - 4;
  let headEnterIndex = 3;
  let index2;
  let enter;
  if ((events[headEnterIndex][1].type === "lineEnding" || events[headEnterIndex][1].type === "space") && (events[tailExitIndex][1].type === "lineEnding" || events[tailExitIndex][1].type === "space")) {
    index2 = headEnterIndex;
    while (++index2 < tailExitIndex) {
      if (events[index2][1].type === "codeTextData") {
        events[headEnterIndex][1].type = "codeTextPadding";
        events[tailExitIndex][1].type = "codeTextPadding";
        headEnterIndex += 2;
        tailExitIndex -= 2;
        break;
      }
    }
  }
  index2 = headEnterIndex - 1;
  tailExitIndex++;
  while (++index2 <= tailExitIndex) {
    if (enter === void 0) {
      if (index2 !== tailExitIndex && events[index2][1].type !== "lineEnding") {
        enter = index2;
      }
    } else if (index2 === tailExitIndex || events[index2][1].type === "lineEnding") {
      events[enter][1].type = "codeTextData";
      if (index2 !== enter + 2) {
        events[enter][1].end = events[index2 - 1][1].end;
        events.splice(enter + 2, index2 - enter - 2);
        tailExitIndex -= index2 - enter - 2;
        index2 = enter + 2;
      }
      enter = void 0;
    }
  }
  return events;
}
function previous(code4) {
  return code4 !== 96 || this.events[this.events.length - 1][1].type === "characterEscape";
}
function tokenizeCodeText(effects, ok2, nok) {
  const self = this;
  let sizeOpen = 0;
  let size;
  let token;
  return start;
  function start(code4) {
    effects.enter("codeText");
    effects.enter("codeTextSequence");
    return sequenceOpen(code4);
  }
  function sequenceOpen(code4) {
    if (code4 === 96) {
      effects.consume(code4);
      sizeOpen++;
      return sequenceOpen;
    }
    effects.exit("codeTextSequence");
    return between2(code4);
  }
  function between2(code4) {
    if (code4 === null) {
      return nok(code4);
    }
    if (code4 === 32) {
      effects.enter("space");
      effects.consume(code4);
      effects.exit("space");
      return between2;
    }
    if (code4 === 96) {
      token = effects.enter("codeTextSequence");
      size = 0;
      return sequenceClose(code4);
    }
    if (markdownLineEnding(code4)) {
      effects.enter("lineEnding");
      effects.consume(code4);
      effects.exit("lineEnding");
      return between2;
    }
    effects.enter("codeTextData");
    return data(code4);
  }
  function data(code4) {
    if (code4 === null || code4 === 32 || code4 === 96 || markdownLineEnding(code4)) {
      effects.exit("codeTextData");
      return between2(code4);
    }
    effects.consume(code4);
    return data;
  }
  function sequenceClose(code4) {
    if (code4 === 96) {
      effects.consume(code4);
      size++;
      return sequenceClose;
    }
    if (size === sizeOpen) {
      effects.exit("codeTextSequence");
      effects.exit("codeText");
      return ok2(code4);
    }
    token.type = "codeTextData";
    return data(code4);
  }
}

// node_modules/.pnpm/micromark-util-subtokenize@2.1.0/node_modules/micromark-util-subtokenize/lib/splice-buffer.js
var SpliceBuffer = class {
  /**
   * @param {ReadonlyArray<T> | null | undefined} [initial]
   *   Initial items (optional).
   * @returns
   *   Splice buffer.
   */
  constructor(initial) {
    this.left = initial ? [...initial] : [];
    this.right = [];
  }
  /**
   * Array access;
   * does not move the cursor.
   *
   * @param {number} index
   *   Index.
   * @return {T}
   *   Item.
   */
  get(index2) {
    if (index2 < 0 || index2 >= this.left.length + this.right.length) {
      throw new RangeError("Cannot access index `" + index2 + "` in a splice buffer of size `" + (this.left.length + this.right.length) + "`");
    }
    if (index2 < this.left.length) return this.left[index2];
    return this.right[this.right.length - index2 + this.left.length - 1];
  }
  /**
   * The length of the splice buffer, one greater than the largest index in the
   * array.
   */
  get length() {
    return this.left.length + this.right.length;
  }
  /**
   * Remove and return `list[0]`;
   * moves the cursor to `0`.
   *
   * @returns {T | undefined}
   *   Item, optional.
   */
  shift() {
    this.setCursor(0);
    return this.right.pop();
  }
  /**
   * Slice the buffer to get an array;
   * does not move the cursor.
   *
   * @param {number} start
   *   Start.
   * @param {number | null | undefined} [end]
   *   End (optional).
   * @returns {Array<T>}
   *   Array of items.
   */
  slice(start, end) {
    const stop = end === null || end === void 0 ? Number.POSITIVE_INFINITY : end;
    if (stop < this.left.length) {
      return this.left.slice(start, stop);
    }
    if (start > this.left.length) {
      return this.right.slice(this.right.length - stop + this.left.length, this.right.length - start + this.left.length).reverse();
    }
    return this.left.slice(start).concat(this.right.slice(this.right.length - stop + this.left.length).reverse());
  }
  /**
   * Mimics the behavior of Array.prototype.splice() except for the change of
   * interface necessary to avoid segfaults when patching in very large arrays.
   *
   * This operation moves cursor is moved to `start` and results in the cursor
   * placed after any inserted items.
   *
   * @param {number} start
   *   Start;
   *   zero-based index at which to start changing the array;
   *   negative numbers count backwards from the end of the array and values
   *   that are out-of bounds are clamped to the appropriate end of the array.
   * @param {number | null | undefined} [deleteCount=0]
   *   Delete count (default: `0`);
   *   maximum number of elements to delete, starting from start.
   * @param {Array<T> | null | undefined} [items=[]]
   *   Items to include in place of the deleted items (default: `[]`).
   * @return {Array<T>}
   *   Any removed items.
   */
  splice(start, deleteCount, items) {
    const count = deleteCount || 0;
    this.setCursor(Math.trunc(start));
    const removed = this.right.splice(this.right.length - count, Number.POSITIVE_INFINITY);
    if (items) chunkedPush(this.left, items);
    return removed.reverse();
  }
  /**
   * Remove and return the highest-numbered item in the array, so
   * `list[list.length - 1]`;
   * Moves the cursor to `length`.
   *
   * @returns {T | undefined}
   *   Item, optional.
   */
  pop() {
    this.setCursor(Number.POSITIVE_INFINITY);
    return this.left.pop();
  }
  /**
   * Inserts a single item to the high-numbered side of the array;
   * moves the cursor to `length`.
   *
   * @param {T} item
   *   Item.
   * @returns {undefined}
   *   Nothing.
   */
  push(item) {
    this.setCursor(Number.POSITIVE_INFINITY);
    this.left.push(item);
  }
  /**
   * Inserts many items to the high-numbered side of the array.
   * Moves the cursor to `length`.
   *
   * @param {Array<T>} items
   *   Items.
   * @returns {undefined}
   *   Nothing.
   */
  pushMany(items) {
    this.setCursor(Number.POSITIVE_INFINITY);
    chunkedPush(this.left, items);
  }
  /**
   * Inserts a single item to the low-numbered side of the array;
   * Moves the cursor to `0`.
   *
   * @param {T} item
   *   Item.
   * @returns {undefined}
   *   Nothing.
   */
  unshift(item) {
    this.setCursor(0);
    this.right.push(item);
  }
  /**
   * Inserts many items to the low-numbered side of the array;
   * moves the cursor to `0`.
   *
   * @param {Array<T>} items
   *   Items.
   * @returns {undefined}
   *   Nothing.
   */
  unshiftMany(items) {
    this.setCursor(0);
    chunkedPush(this.right, items.reverse());
  }
  /**
   * Move the cursor to a specific position in the array. Requires
   * time proportional to the distance moved.
   *
   * If `n < 0`, the cursor will end up at the beginning.
   * If `n > length`, the cursor will end up at the end.
   *
   * @param {number} n
   *   Position.
   * @return {undefined}
   *   Nothing.
   */
  setCursor(n) {
    if (n === this.left.length || n > this.left.length && this.right.length === 0 || n < 0 && this.left.length === 0) return;
    if (n < this.left.length) {
      const removed = this.left.splice(n, Number.POSITIVE_INFINITY);
      chunkedPush(this.right, removed.reverse());
    } else {
      const removed = this.right.splice(this.left.length + this.right.length - n, Number.POSITIVE_INFINITY);
      chunkedPush(this.left, removed.reverse());
    }
  }
};
function chunkedPush(list4, right) {
  let chunkStart = 0;
  if (right.length < 1e4) {
    list4.push(...right);
  } else {
    while (chunkStart < right.length) {
      list4.push(...right.slice(chunkStart, chunkStart + 1e4));
      chunkStart += 1e4;
    }
  }
}

// node_modules/.pnpm/micromark-util-subtokenize@2.1.0/node_modules/micromark-util-subtokenize/index.js
function subtokenize(eventsArray) {
  const jumps = {};
  let index2 = -1;
  let event;
  let lineIndex;
  let otherIndex;
  let otherEvent;
  let parameters;
  let subevents;
  let more;
  const events = new SpliceBuffer(eventsArray);
  while (++index2 < events.length) {
    while (index2 in jumps) {
      index2 = jumps[index2];
    }
    event = events.get(index2);
    if (index2 && event[1].type === "chunkFlow" && events.get(index2 - 1)[1].type === "listItemPrefix") {
      subevents = event[1]._tokenizer.events;
      otherIndex = 0;
      if (otherIndex < subevents.length && subevents[otherIndex][1].type === "lineEndingBlank") {
        otherIndex += 2;
      }
      if (otherIndex < subevents.length && subevents[otherIndex][1].type === "content") {
        while (++otherIndex < subevents.length) {
          if (subevents[otherIndex][1].type === "content") {
            break;
          }
          if (subevents[otherIndex][1].type === "chunkText") {
            subevents[otherIndex][1]._isInFirstContentOfListItem = true;
            otherIndex++;
          }
        }
      }
    }
    if (event[0] === "enter") {
      if (event[1].contentType) {
        Object.assign(jumps, subcontent(events, index2));
        index2 = jumps[index2];
        more = true;
      }
    } else if (event[1]._container) {
      otherIndex = index2;
      lineIndex = void 0;
      while (otherIndex--) {
        otherEvent = events.get(otherIndex);
        if (otherEvent[1].type === "lineEnding" || otherEvent[1].type === "lineEndingBlank") {
          if (otherEvent[0] === "enter") {
            if (lineIndex) {
              events.get(lineIndex)[1].type = "lineEndingBlank";
            }
            otherEvent[1].type = "lineEnding";
            lineIndex = otherIndex;
          }
        } else if (otherEvent[1].type === "linePrefix" || otherEvent[1].type === "listItemIndent") {
        } else {
          break;
        }
      }
      if (lineIndex) {
        event[1].end = {
          ...events.get(lineIndex)[1].start
        };
        parameters = events.slice(lineIndex, index2);
        parameters.unshift(event);
        events.splice(lineIndex, index2 - lineIndex + 1, parameters);
      }
    }
  }
  splice(eventsArray, 0, Number.POSITIVE_INFINITY, events.slice(0));
  return !more;
}
function subcontent(events, eventIndex) {
  const token = events.get(eventIndex)[1];
  const context = events.get(eventIndex)[2];
  let startPosition = eventIndex - 1;
  const startPositions = [];
  let tokenizer = token._tokenizer;
  if (!tokenizer) {
    tokenizer = context.parser[token.contentType](token.start);
    if (token._contentTypeTextTrailing) {
      tokenizer._contentTypeTextTrailing = true;
    }
  }
  const childEvents = tokenizer.events;
  const jumps = [];
  const gaps = {};
  let stream;
  let previous2;
  let index2 = -1;
  let current = token;
  let adjust = 0;
  let start = 0;
  const breaks = [start];
  while (current) {
    while (events.get(++startPosition)[1] !== current) {
    }
    startPositions.push(startPosition);
    if (!current._tokenizer) {
      stream = context.sliceStream(current);
      if (!current.next) {
        stream.push(null);
      }
      if (previous2) {
        tokenizer.defineSkip(current.start);
      }
      if (current._isInFirstContentOfListItem) {
        tokenizer._gfmTasklistFirstContentOfListItem = true;
      }
      tokenizer.write(stream);
      if (current._isInFirstContentOfListItem) {
        tokenizer._gfmTasklistFirstContentOfListItem = void 0;
      }
    }
    previous2 = current;
    current = current.next;
  }
  current = token;
  while (++index2 < childEvents.length) {
    if (
      // Find a void token that includes a break.
      childEvents[index2][0] === "exit" && childEvents[index2 - 1][0] === "enter" && childEvents[index2][1].type === childEvents[index2 - 1][1].type && childEvents[index2][1].start.line !== childEvents[index2][1].end.line
    ) {
      start = index2 + 1;
      breaks.push(start);
      current._tokenizer = void 0;
      current.previous = void 0;
      current = current.next;
    }
  }
  tokenizer.events = [];
  if (current) {
    current._tokenizer = void 0;
    current.previous = void 0;
  } else {
    breaks.pop();
  }
  index2 = breaks.length;
  while (index2--) {
    const slice2 = childEvents.slice(breaks[index2], breaks[index2 + 1]);
    const start2 = startPositions.pop();
    jumps.push([start2, start2 + slice2.length - 1]);
    events.splice(start2, 2, slice2);
  }
  jumps.reverse();
  index2 = -1;
  while (++index2 < jumps.length) {
    gaps[adjust + jumps[index2][0]] = adjust + jumps[index2][1];
    adjust += jumps[index2][1] - jumps[index2][0] - 1;
  }
  return gaps;
}

// node_modules/.pnpm/micromark-core-commonmark@2.0.4/node_modules/micromark-core-commonmark/lib/content.js
var content2 = {
  resolve: resolveContent,
  tokenize: tokenizeContent
};
var continuationConstruct = {
  partial: true,
  tokenize: tokenizeContinuation
};
function resolveContent(events) {
  subtokenize(events);
  return events;
}
function tokenizeContent(effects, ok2) {
  let previous2;
  return chunkStart;
  function chunkStart(code4) {
    effects.enter("content");
    previous2 = effects.enter("chunkContent", {
      contentType: "content"
    });
    return chunkInside(code4);
  }
  function chunkInside(code4) {
    if (code4 === null) {
      return contentEnd(code4);
    }
    if (markdownLineEnding(code4)) {
      return effects.check(continuationConstruct, contentContinue, contentEnd)(code4);
    }
    effects.consume(code4);
    return chunkInside;
  }
  function contentEnd(code4) {
    effects.exit("chunkContent");
    effects.exit("content");
    return ok2(code4);
  }
  function contentContinue(code4) {
    effects.consume(code4);
    effects.exit("chunkContent");
    previous2.next = effects.enter("chunkContent", {
      contentType: "content",
      previous: previous2
    });
    previous2 = previous2.next;
    return chunkInside;
  }
}
function tokenizeContinuation(effects, ok2, nok) {
  const self = this;
  return startLookahead;
  function startLookahead(code4) {
    effects.exit("chunkContent");
    effects.enter("lineEnding");
    effects.consume(code4);
    effects.exit("lineEnding");
    return factorySpace(effects, prefixed, "linePrefix");
  }
  function prefixed(code4) {
    if (code4 === null || markdownLineEnding(code4)) {
      return nok(code4);
    }
    const tail = self.events[self.events.length - 1];
    if (!self.parser.constructs.disable.null.includes("codeIndented") && tail && tail[1].type === "linePrefix" && tail[2].sliceSerialize(tail[1], true).length >= 4) {
      return ok2(code4);
    }
    return effects.interrupt(self.parser.constructs.flow, nok, ok2)(code4);
  }
}

// node_modules/.pnpm/micromark-factory-destination@2.0.1/node_modules/micromark-factory-destination/index.js
function factoryDestination(effects, ok2, nok, type, literalType, literalMarkerType, rawType, stringType, max) {
  const limit = max || Number.POSITIVE_INFINITY;
  let balance = 0;
  return start;
  function start(code4) {
    if (code4 === 60) {
      effects.enter(type);
      effects.enter(literalType);
      effects.enter(literalMarkerType);
      effects.consume(code4);
      effects.exit(literalMarkerType);
      return enclosedBefore;
    }
    if (code4 === null || code4 === 32 || code4 === 41 || asciiControl(code4)) {
      return nok(code4);
    }
    effects.enter(type);
    effects.enter(rawType);
    effects.enter(stringType);
    effects.enter("chunkString", {
      contentType: "string"
    });
    return raw(code4);
  }
  function enclosedBefore(code4) {
    if (code4 === 62) {
      effects.enter(literalMarkerType);
      effects.consume(code4);
      effects.exit(literalMarkerType);
      effects.exit(literalType);
      effects.exit(type);
      return ok2;
    }
    effects.enter(stringType);
    effects.enter("chunkString", {
      contentType: "string"
    });
    return enclosed(code4);
  }
  function enclosed(code4) {
    if (code4 === 62) {
      effects.exit("chunkString");
      effects.exit(stringType);
      return enclosedBefore(code4);
    }
    if (code4 === null || code4 === 60 || markdownLineEnding(code4)) {
      return nok(code4);
    }
    effects.consume(code4);
    return code4 === 92 ? enclosedEscape : enclosed;
  }
  function enclosedEscape(code4) {
    if (code4 === 60 || code4 === 62 || code4 === 92) {
      effects.consume(code4);
      return enclosed;
    }
    return enclosed(code4);
  }
  function raw(code4) {
    if (!balance && (code4 === null || code4 === 41 || markdownLineEndingOrSpace(code4))) {
      effects.exit("chunkString");
      effects.exit(stringType);
      effects.exit(rawType);
      effects.exit(type);
      return ok2(code4);
    }
    if (balance < limit && code4 === 40) {
      effects.consume(code4);
      balance++;
      return raw;
    }
    if (code4 === 41) {
      effects.consume(code4);
      balance--;
      return raw;
    }
    if (code4 === null || code4 === 32 || code4 === 40 || asciiControl(code4)) {
      return nok(code4);
    }
    effects.consume(code4);
    return code4 === 92 ? rawEscape : raw;
  }
  function rawEscape(code4) {
    if (code4 === 40 || code4 === 41 || code4 === 92) {
      effects.consume(code4);
      return raw;
    }
    return raw(code4);
  }
}

// node_modules/.pnpm/micromark-factory-label@2.0.1/node_modules/micromark-factory-label/index.js
function factoryLabel(effects, ok2, nok, type, markerType, stringType) {
  const self = this;
  let size = 0;
  let seen;
  return start;
  function start(code4) {
    effects.enter(type);
    effects.enter(markerType);
    effects.consume(code4);
    effects.exit(markerType);
    effects.enter(stringType);
    return atBreak;
  }
  function atBreak(code4) {
    if (size > 999 || code4 === null || code4 === 91 || code4 === 93 && !seen || // To do: remove in the future once we’ve switched from
    // `micromark-extension-footnote` to `micromark-extension-gfm-footnote`,
    // which doesn’t need this.
    // Hidden footnotes hook.
    /* c8 ignore next 3 */
    code4 === 94 && !size && "_hiddenFootnoteSupport" in self.parser.constructs) {
      return nok(code4);
    }
    if (code4 === 93) {
      effects.exit(stringType);
      effects.enter(markerType);
      effects.consume(code4);
      effects.exit(markerType);
      effects.exit(type);
      return ok2;
    }
    if (markdownLineEnding(code4)) {
      effects.enter("lineEnding");
      effects.consume(code4);
      effects.exit("lineEnding");
      return atBreak;
    }
    effects.enter("chunkString", {
      contentType: "string"
    });
    return labelInside(code4);
  }
  function labelInside(code4) {
    if (code4 === null || code4 === 91 || code4 === 93 || markdownLineEnding(code4) || size++ > 999) {
      effects.exit("chunkString");
      return atBreak(code4);
    }
    effects.consume(code4);
    if (!seen) seen = !markdownSpace(code4);
    return code4 === 92 ? labelEscape : labelInside;
  }
  function labelEscape(code4) {
    if (code4 === 91 || code4 === 92 || code4 === 93) {
      effects.consume(code4);
      size++;
      return labelInside;
    }
    return labelInside(code4);
  }
}

// node_modules/.pnpm/micromark-factory-title@2.0.1/node_modules/micromark-factory-title/index.js
function factoryTitle(effects, ok2, nok, type, markerType, stringType) {
  let marker;
  return start;
  function start(code4) {
    if (code4 === 34 || code4 === 39 || code4 === 40) {
      effects.enter(type);
      effects.enter(markerType);
      effects.consume(code4);
      effects.exit(markerType);
      marker = code4 === 40 ? 41 : code4;
      return begin;
    }
    return nok(code4);
  }
  function begin(code4) {
    if (code4 === marker) {
      effects.enter(markerType);
      effects.consume(code4);
      effects.exit(markerType);
      effects.exit(type);
      return ok2;
    }
    effects.enter(stringType);
    return atBreak(code4);
  }
  function atBreak(code4) {
    if (code4 === marker) {
      effects.exit(stringType);
      return begin(marker);
    }
    if (code4 === null) {
      return nok(code4);
    }
    if (markdownLineEnding(code4)) {
      effects.enter("lineEnding");
      effects.consume(code4);
      effects.exit("lineEnding");
      return factorySpace(effects, atBreak, "linePrefix");
    }
    effects.enter("chunkString", {
      contentType: "string"
    });
    return inside(code4);
  }
  function inside(code4) {
    if (code4 === marker || code4 === null || markdownLineEnding(code4)) {
      effects.exit("chunkString");
      return atBreak(code4);
    }
    effects.consume(code4);
    return code4 === 92 ? escape : inside;
  }
  function escape(code4) {
    if (code4 === marker || code4 === 92) {
      effects.consume(code4);
      return inside;
    }
    return inside(code4);
  }
}

// node_modules/.pnpm/micromark-factory-whitespace@2.0.1/node_modules/micromark-factory-whitespace/index.js
function factoryWhitespace(effects, ok2) {
  let seen;
  return start;
  function start(code4) {
    if (markdownLineEnding(code4)) {
      effects.enter("lineEnding");
      effects.consume(code4);
      effects.exit("lineEnding");
      seen = true;
      return start;
    }
    if (markdownSpace(code4)) {
      return factorySpace(effects, start, seen ? "linePrefix" : "lineSuffix")(code4);
    }
    return ok2(code4);
  }
}

// node_modules/.pnpm/micromark-core-commonmark@2.0.4/node_modules/micromark-core-commonmark/lib/definition.js
var definition = {
  name: "definition",
  tokenize: tokenizeDefinition
};
var titleBefore = {
  partial: true,
  tokenize: tokenizeTitleBefore
};
function tokenizeDefinition(effects, ok2, nok) {
  const self = this;
  let identifier;
  return start;
  function start(code4) {
    effects.enter("definition");
    return before(code4);
  }
  function before(code4) {
    return factoryLabel.call(
      self,
      effects,
      labelAfter,
      // Note: we don’t need to reset the way `markdown-rs` does.
      nok,
      "definitionLabel",
      "definitionLabelMarker",
      "definitionLabelString"
    )(code4);
  }
  function labelAfter(code4) {
    identifier = normalizeIdentifier(self.sliceSerialize(self.events[self.events.length - 1][1]).slice(1, -1));
    if (code4 === 58) {
      effects.enter("definitionMarker");
      effects.consume(code4);
      effects.exit("definitionMarker");
      return markerAfter;
    }
    return nok(code4);
  }
  function markerAfter(code4) {
    return markdownLineEndingOrSpace(code4) ? factoryWhitespace(effects, destinationBefore)(code4) : destinationBefore(code4);
  }
  function destinationBefore(code4) {
    return factoryDestination(
      effects,
      destinationAfter,
      // Note: we don’t need to reset the way `markdown-rs` does.
      nok,
      "definitionDestination",
      "definitionDestinationLiteral",
      "definitionDestinationLiteralMarker",
      "definitionDestinationRaw",
      "definitionDestinationString"
    )(code4);
  }
  function destinationAfter(code4) {
    return effects.attempt(titleBefore, after, after)(code4);
  }
  function after(code4) {
    return markdownSpace(code4) ? factorySpace(effects, afterWhitespace, "whitespace")(code4) : afterWhitespace(code4);
  }
  function afterWhitespace(code4) {
    if (code4 === null || markdownLineEnding(code4)) {
      effects.exit("definition");
      self.parser.defined.push(identifier);
      return ok2(code4);
    }
    return nok(code4);
  }
}
function tokenizeTitleBefore(effects, ok2, nok) {
  return titleBefore2;
  function titleBefore2(code4) {
    return markdownLineEndingOrSpace(code4) ? factoryWhitespace(effects, beforeMarker)(code4) : nok(code4);
  }
  function beforeMarker(code4) {
    return factoryTitle(effects, titleAfter, nok, "definitionTitle", "definitionTitleMarker", "definitionTitleString")(code4);
  }
  function titleAfter(code4) {
    return markdownSpace(code4) ? factorySpace(effects, titleAfterOptionalWhitespace, "whitespace")(code4) : titleAfterOptionalWhitespace(code4);
  }
  function titleAfterOptionalWhitespace(code4) {
    return code4 === null || markdownLineEnding(code4) ? ok2(code4) : nok(code4);
  }
}

// node_modules/.pnpm/micromark-core-commonmark@2.0.4/node_modules/micromark-core-commonmark/lib/hard-break-escape.js
var hardBreakEscape = {
  name: "hardBreakEscape",
  tokenize: tokenizeHardBreakEscape
};
function tokenizeHardBreakEscape(effects, ok2, nok) {
  return start;
  function start(code4) {
    effects.enter("hardBreakEscape");
    effects.consume(code4);
    return after;
  }
  function after(code4) {
    if (markdownLineEnding(code4)) {
      effects.exit("hardBreakEscape");
      return ok2(code4);
    }
    return nok(code4);
  }
}

// node_modules/.pnpm/micromark-core-commonmark@2.0.4/node_modules/micromark-core-commonmark/lib/heading-atx.js
var headingAtx = {
  name: "headingAtx",
  resolve: resolveHeadingAtx,
  tokenize: tokenizeHeadingAtx
};
function resolveHeadingAtx(events, context) {
  let contentEnd = events.length - 2;
  let contentStart = 3;
  if (events[contentStart][1].type === "whitespace") {
    contentStart += 2;
  }
  if (contentEnd - 2 > contentStart && events[contentEnd][1].type === "whitespace") {
    contentEnd -= 2;
  }
  if (events[contentEnd][1].type === "atxHeadingSequence" && (contentStart === contentEnd - 1 || contentEnd - 4 > contentStart && events[contentEnd - 2][1].type === "whitespace")) {
    contentEnd -= contentStart + 1 === contentEnd ? 2 : 4;
  }
  if (contentEnd > contentStart) {
    const content3 = {
      type: "atxHeadingText",
      start: events[contentStart][1].start,
      end: events[contentEnd][1].end
    };
    const text4 = {
      type: "chunkText",
      start: events[contentStart][1].start,
      end: events[contentEnd][1].end,
      contentType: "text"
    };
    splice(events, contentStart, contentEnd - contentStart + 1, [["enter", content3, context], ["enter", text4, context], ["exit", text4, context], ["exit", content3, context]]);
  }
  return events;
}
function tokenizeHeadingAtx(effects, ok2, nok) {
  let size = 0;
  return start;
  function start(code4) {
    effects.enter("atxHeading");
    return before(code4);
  }
  function before(code4) {
    effects.enter("atxHeadingSequence");
    return sequenceOpen(code4);
  }
  function sequenceOpen(code4) {
    if (code4 === 35 && size++ < 6) {
      effects.consume(code4);
      return sequenceOpen;
    }
    if (code4 === null || markdownLineEndingOrSpace(code4)) {
      effects.exit("atxHeadingSequence");
      return atBreak(code4);
    }
    return nok(code4);
  }
  function atBreak(code4) {
    if (code4 === 35) {
      effects.enter("atxHeadingSequence");
      return sequenceFurther(code4);
    }
    if (code4 === null || markdownLineEnding(code4)) {
      effects.exit("atxHeading");
      return ok2(code4);
    }
    if (markdownSpace(code4)) {
      return factorySpace(effects, atBreak, "whitespace")(code4);
    }
    effects.enter("atxHeadingText");
    return data(code4);
  }
  function sequenceFurther(code4) {
    if (code4 === 35) {
      effects.consume(code4);
      return sequenceFurther;
    }
    effects.exit("atxHeadingSequence");
    return atBreak(code4);
  }
  function data(code4) {
    if (code4 === null || code4 === 35 || markdownLineEndingOrSpace(code4)) {
      effects.exit("atxHeadingText");
      return atBreak(code4);
    }
    effects.consume(code4);
    return data;
  }
}

// node_modules/.pnpm/micromark-util-html-tag-name@2.0.1/node_modules/micromark-util-html-tag-name/index.js
var htmlBlockNames = [
  "address",
  "article",
  "aside",
  "base",
  "basefont",
  "blockquote",
  "body",
  "caption",
  "center",
  "col",
  "colgroup",
  "dd",
  "details",
  "dialog",
  "dir",
  "div",
  "dl",
  "dt",
  "fieldset",
  "figcaption",
  "figure",
  "footer",
  "form",
  "frame",
  "frameset",
  "h1",
  "h2",
  "h3",
  "h4",
  "h5",
  "h6",
  "head",
  "header",
  "hr",
  "html",
  "iframe",
  "legend",
  "li",
  "link",
  "main",
  "menu",
  "menuitem",
  "nav",
  "noframes",
  "ol",
  "optgroup",
  "option",
  "p",
  "param",
  "search",
  "section",
  "summary",
  "table",
  "tbody",
  "td",
  "tfoot",
  "th",
  "thead",
  "title",
  "tr",
  "track",
  "ul"
];
var htmlRawNames = ["pre", "script", "style", "textarea"];

// node_modules/.pnpm/micromark-core-commonmark@2.0.4/node_modules/micromark-core-commonmark/lib/html-flow.js
var htmlFlow = {
  concrete: true,
  name: "htmlFlow",
  resolveTo: resolveToHtmlFlow,
  tokenize: tokenizeHtmlFlow
};
var blankLineBefore = {
  partial: true,
  tokenize: tokenizeBlankLineBefore
};
function resolveToHtmlFlow(events) {
  let index2 = events.length;
  while (index2--) {
    if (events[index2][0] === "enter" && events[index2][1].type === "htmlFlow") {
      break;
    }
  }
  if (index2 > 1 && events[index2 - 2][1].type === "linePrefix") {
    events[index2][1].start = events[index2 - 2][1].start;
    events[index2 + 1][1].start = events[index2 - 2][1].start;
    events.splice(index2 - 2, 2);
  }
  return events;
}
function tokenizeHtmlFlow(effects, ok2, nok) {
  const self = this;
  let marker;
  let closingTag;
  let buffer;
  let index2;
  let markerB;
  return start;
  function start(code4) {
    return before(code4);
  }
  function before(code4) {
    effects.enter("htmlFlow");
    effects.enter("htmlFlowData");
    effects.consume(code4);
    return open;
  }
  function open(code4) {
    if (code4 === 33) {
      effects.consume(code4);
      return declarationOpen;
    }
    if (code4 === 47) {
      effects.consume(code4);
      closingTag = true;
      return tagCloseStart;
    }
    if (code4 === 63) {
      effects.consume(code4);
      marker = 3;
      return self.interrupt ? ok2 : continuationDeclarationInside;
    }
    if (asciiAlpha(code4)) {
      effects.consume(code4);
      buffer = String.fromCharCode(code4);
      return tagName;
    }
    return nok(code4);
  }
  function declarationOpen(code4) {
    if (code4 === 45) {
      effects.consume(code4);
      marker = 2;
      return commentOpenInside;
    }
    if (code4 === 91) {
      effects.consume(code4);
      marker = 5;
      index2 = 0;
      return cdataOpenInside;
    }
    if (asciiAlpha(code4)) {
      effects.consume(code4);
      marker = 4;
      return self.interrupt ? ok2 : continuationDeclarationInside;
    }
    return nok(code4);
  }
  function commentOpenInside(code4) {
    if (code4 === 45) {
      effects.consume(code4);
      return self.interrupt ? ok2 : continuationDeclarationInside;
    }
    return nok(code4);
  }
  function cdataOpenInside(code4) {
    const value = "CDATA[";
    if (code4 === value.charCodeAt(index2++)) {
      effects.consume(code4);
      if (index2 === value.length) {
        return self.interrupt ? ok2 : continuation;
      }
      return cdataOpenInside;
    }
    return nok(code4);
  }
  function tagCloseStart(code4) {
    if (asciiAlpha(code4)) {
      effects.consume(code4);
      buffer = String.fromCharCode(code4);
      return tagName;
    }
    return nok(code4);
  }
  function tagName(code4) {
    if (code4 === null || code4 === 47 || code4 === 62 || markdownLineEndingOrSpace(code4)) {
      const slash = code4 === 47;
      const name = buffer.toLowerCase();
      if (!slash && !closingTag && htmlRawNames.includes(name)) {
        marker = 1;
        return self.interrupt ? ok2(code4) : continuation(code4);
      }
      if (htmlBlockNames.includes(buffer.toLowerCase())) {
        marker = 6;
        if (slash) {
          effects.consume(code4);
          return basicSelfClosing;
        }
        return self.interrupt ? ok2(code4) : continuation(code4);
      }
      marker = 7;
      return self.interrupt && !self.parser.lazy[self.now().line] ? nok(code4) : closingTag ? completeClosingTagAfter(code4) : completeAttributeNameBefore(code4);
    }
    if (code4 === 45 || asciiAlphanumeric(code4)) {
      effects.consume(code4);
      buffer += String.fromCharCode(code4);
      return tagName;
    }
    return nok(code4);
  }
  function basicSelfClosing(code4) {
    if (code4 === 62) {
      effects.consume(code4);
      return self.interrupt ? ok2 : continuation;
    }
    return nok(code4);
  }
  function completeClosingTagAfter(code4) {
    if (markdownSpace(code4)) {
      effects.consume(code4);
      return completeClosingTagAfter;
    }
    return completeEnd(code4);
  }
  function completeAttributeNameBefore(code4) {
    if (code4 === 47) {
      effects.consume(code4);
      return completeEnd;
    }
    if (code4 === 58 || code4 === 95 || asciiAlpha(code4)) {
      effects.consume(code4);
      return completeAttributeName;
    }
    if (markdownSpace(code4)) {
      effects.consume(code4);
      return completeAttributeNameBefore;
    }
    return completeEnd(code4);
  }
  function completeAttributeName(code4) {
    if (code4 === 45 || code4 === 46 || code4 === 58 || code4 === 95 || asciiAlphanumeric(code4)) {
      effects.consume(code4);
      return completeAttributeName;
    }
    return completeAttributeNameAfter(code4);
  }
  function completeAttributeNameAfter(code4) {
    if (code4 === 61) {
      effects.consume(code4);
      return completeAttributeValueBefore;
    }
    if (markdownSpace(code4)) {
      effects.consume(code4);
      return completeAttributeNameAfter;
    }
    return completeAttributeNameBefore(code4);
  }
  function completeAttributeValueBefore(code4) {
    if (code4 === null || code4 === 60 || code4 === 61 || code4 === 62 || code4 === 96) {
      return nok(code4);
    }
    if (code4 === 34 || code4 === 39) {
      effects.consume(code4);
      markerB = code4;
      return completeAttributeValueQuoted;
    }
    if (markdownSpace(code4)) {
      effects.consume(code4);
      return completeAttributeValueBefore;
    }
    return completeAttributeValueUnquoted(code4);
  }
  function completeAttributeValueQuoted(code4) {
    if (code4 === markerB) {
      effects.consume(code4);
      markerB = null;
      return completeAttributeValueQuotedAfter;
    }
    if (code4 === null || markdownLineEnding(code4)) {
      return nok(code4);
    }
    effects.consume(code4);
    return completeAttributeValueQuoted;
  }
  function completeAttributeValueUnquoted(code4) {
    if (code4 === null || code4 === 34 || code4 === 39 || code4 === 47 || code4 === 60 || code4 === 61 || code4 === 62 || code4 === 96 || markdownLineEndingOrSpace(code4)) {
      return completeAttributeNameAfter(code4);
    }
    effects.consume(code4);
    return completeAttributeValueUnquoted;
  }
  function completeAttributeValueQuotedAfter(code4) {
    if (code4 === 47 || code4 === 62 || markdownSpace(code4)) {
      return completeAttributeNameBefore(code4);
    }
    return nok(code4);
  }
  function completeEnd(code4) {
    if (code4 === 62) {
      effects.consume(code4);
      return completeAfter;
    }
    return nok(code4);
  }
  function completeAfter(code4) {
    if (code4 === null || markdownLineEnding(code4)) {
      return continuation(code4);
    }
    if (markdownSpace(code4)) {
      effects.consume(code4);
      return completeAfter;
    }
    return nok(code4);
  }
  function continuation(code4) {
    if (code4 === 45 && marker === 2) {
      effects.consume(code4);
      return continuationCommentInside;
    }
    if (code4 === 60 && marker === 1) {
      effects.consume(code4);
      return continuationRawTagOpen;
    }
    if (code4 === 62 && marker === 4) {
      effects.consume(code4);
      return continuationClose;
    }
    if (code4 === 63 && marker === 3) {
      effects.consume(code4);
      return continuationDeclarationInside;
    }
    if (code4 === 93 && marker === 5) {
      effects.consume(code4);
      return continuationCdataInside;
    }
    if (markdownLineEnding(code4) && (marker === 6 || marker === 7)) {
      effects.exit("htmlFlowData");
      return effects.check(blankLineBefore, continuationAfter, continuationStart)(code4);
    }
    if (code4 === null || markdownLineEnding(code4)) {
      effects.exit("htmlFlowData");
      return continuationStart(code4);
    }
    effects.consume(code4);
    return continuation;
  }
  function continuationStart(code4) {
    return effects.check(nonLazyContinuation, continuationStartNonLazy, continuationAfter)(code4);
  }
  function continuationStartNonLazy(code4) {
    effects.enter("lineEnding");
    effects.consume(code4);
    effects.exit("lineEnding");
    return continuationBefore;
  }
  function continuationBefore(code4) {
    if (code4 === null || markdownLineEnding(code4)) {
      return continuationStart(code4);
    }
    effects.enter("htmlFlowData");
    return continuation(code4);
  }
  function continuationCommentInside(code4) {
    if (code4 === 45) {
      effects.consume(code4);
      return continuationDeclarationInside;
    }
    return continuation(code4);
  }
  function continuationRawTagOpen(code4) {
    if (code4 === 47) {
      effects.consume(code4);
      buffer = "";
      return continuationRawEndTag;
    }
    return continuation(code4);
  }
  function continuationRawEndTag(code4) {
    if (code4 === 62) {
      const name = buffer.toLowerCase();
      if (htmlRawNames.includes(name)) {
        effects.consume(code4);
        return continuationClose;
      }
      return continuation(code4);
    }
    if (asciiAlpha(code4) && buffer.length < 8) {
      effects.consume(code4);
      buffer += String.fromCharCode(code4);
      return continuationRawEndTag;
    }
    return continuation(code4);
  }
  function continuationCdataInside(code4) {
    if (code4 === 93) {
      effects.consume(code4);
      return continuationDeclarationInside;
    }
    return continuation(code4);
  }
  function continuationDeclarationInside(code4) {
    if (code4 === 62) {
      effects.consume(code4);
      return continuationClose;
    }
    if (code4 === 45 && marker === 2) {
      effects.consume(code4);
      return continuationDeclarationInside;
    }
    return continuation(code4);
  }
  function continuationClose(code4) {
    if (code4 === null || markdownLineEnding(code4)) {
      effects.exit("htmlFlowData");
      return continuationAfter(code4);
    }
    effects.consume(code4);
    return continuationClose;
  }
  function continuationAfter(code4) {
    effects.exit("htmlFlow");
    return ok2(code4);
  }
}
function tokenizeBlankLineBefore(effects, ok2, nok) {
  return start;
  function start(code4) {
    effects.enter("lineEnding");
    effects.consume(code4);
    effects.exit("lineEnding");
    return effects.attempt(blankLine, ok2, nok);
  }
}

// node_modules/.pnpm/micromark-core-commonmark@2.0.4/node_modules/micromark-core-commonmark/lib/html-text.js
var htmlText = {
  name: "htmlText",
  tokenize: tokenizeHtmlText
};
function tokenizeHtmlText(effects, ok2, nok) {
  const self = this;
  let marker;
  let index2;
  let returnState;
  return start;
  function start(code4) {
    effects.enter("htmlText");
    effects.enter("htmlTextData");
    effects.consume(code4);
    return open;
  }
  function open(code4) {
    if (code4 === 33) {
      effects.consume(code4);
      return declarationOpen;
    }
    if (code4 === 47) {
      effects.consume(code4);
      return tagCloseStart;
    }
    if (code4 === 63) {
      effects.consume(code4);
      return instruction;
    }
    if (asciiAlpha(code4)) {
      effects.consume(code4);
      return tagOpen;
    }
    return nok(code4);
  }
  function declarationOpen(code4) {
    if (code4 === 45) {
      effects.consume(code4);
      return commentOpenInside;
    }
    if (code4 === 91) {
      effects.consume(code4);
      index2 = 0;
      return cdataOpenInside;
    }
    if (asciiAlpha(code4)) {
      effects.consume(code4);
      return declaration;
    }
    return nok(code4);
  }
  function commentOpenInside(code4) {
    if (code4 === 45) {
      effects.consume(code4);
      return commentEnd;
    }
    return nok(code4);
  }
  function comment(code4) {
    if (code4 === null) {
      return nok(code4);
    }
    if (code4 === 45) {
      effects.consume(code4);
      return commentClose;
    }
    if (markdownLineEnding(code4)) {
      returnState = comment;
      return lineEndingBefore(code4);
    }
    effects.consume(code4);
    return comment;
  }
  function commentClose(code4) {
    if (code4 === 45) {
      effects.consume(code4);
      return commentEnd;
    }
    return comment(code4);
  }
  function commentEnd(code4) {
    return code4 === 62 ? end(code4) : code4 === 45 ? commentClose(code4) : comment(code4);
  }
  function cdataOpenInside(code4) {
    const value = "CDATA[";
    if (code4 === value.charCodeAt(index2++)) {
      effects.consume(code4);
      return index2 === value.length ? cdata : cdataOpenInside;
    }
    return nok(code4);
  }
  function cdata(code4) {
    if (code4 === null) {
      return nok(code4);
    }
    if (code4 === 93) {
      effects.consume(code4);
      return cdataClose;
    }
    if (markdownLineEnding(code4)) {
      returnState = cdata;
      return lineEndingBefore(code4);
    }
    effects.consume(code4);
    return cdata;
  }
  function cdataClose(code4) {
    if (code4 === 93) {
      effects.consume(code4);
      return cdataEnd;
    }
    return cdata(code4);
  }
  function cdataEnd(code4) {
    if (code4 === 62) {
      return end(code4);
    }
    if (code4 === 93) {
      effects.consume(code4);
      return cdataEnd;
    }
    return cdata(code4);
  }
  function declaration(code4) {
    if (code4 === null || code4 === 62) {
      return end(code4);
    }
    if (markdownLineEnding(code4)) {
      returnState = declaration;
      return lineEndingBefore(code4);
    }
    effects.consume(code4);
    return declaration;
  }
  function instruction(code4) {
    if (code4 === null) {
      return nok(code4);
    }
    if (code4 === 63) {
      effects.consume(code4);
      return instructionClose;
    }
    if (markdownLineEnding(code4)) {
      returnState = instruction;
      return lineEndingBefore(code4);
    }
    effects.consume(code4);
    return instruction;
  }
  function instructionClose(code4) {
    return code4 === 62 ? end(code4) : instruction(code4);
  }
  function tagCloseStart(code4) {
    if (asciiAlpha(code4)) {
      effects.consume(code4);
      return tagClose;
    }
    return nok(code4);
  }
  function tagClose(code4) {
    if (code4 === 45 || asciiAlphanumeric(code4)) {
      effects.consume(code4);
      return tagClose;
    }
    return tagCloseBetween(code4);
  }
  function tagCloseBetween(code4) {
    if (markdownLineEnding(code4)) {
      returnState = tagCloseBetween;
      return lineEndingBefore(code4);
    }
    if (markdownSpace(code4)) {
      effects.consume(code4);
      return tagCloseBetween;
    }
    return end(code4);
  }
  function tagOpen(code4) {
    if (code4 === 45 || asciiAlphanumeric(code4)) {
      effects.consume(code4);
      return tagOpen;
    }
    if (code4 === 47 || code4 === 62 || markdownLineEndingOrSpace(code4)) {
      return tagOpenBetween(code4);
    }
    return nok(code4);
  }
  function tagOpenBetween(code4) {
    if (code4 === 47) {
      effects.consume(code4);
      return end;
    }
    if (code4 === 58 || code4 === 95 || asciiAlpha(code4)) {
      effects.consume(code4);
      return tagOpenAttributeName;
    }
    if (markdownLineEnding(code4)) {
      returnState = tagOpenBetween;
      return lineEndingBefore(code4);
    }
    if (markdownSpace(code4)) {
      effects.consume(code4);
      return tagOpenBetween;
    }
    return end(code4);
  }
  function tagOpenAttributeName(code4) {
    if (code4 === 45 || code4 === 46 || code4 === 58 || code4 === 95 || asciiAlphanumeric(code4)) {
      effects.consume(code4);
      return tagOpenAttributeName;
    }
    return tagOpenAttributeNameAfter(code4);
  }
  function tagOpenAttributeNameAfter(code4) {
    if (code4 === 61) {
      effects.consume(code4);
      return tagOpenAttributeValueBefore;
    }
    if (markdownLineEnding(code4)) {
      returnState = tagOpenAttributeNameAfter;
      return lineEndingBefore(code4);
    }
    if (markdownSpace(code4)) {
      effects.consume(code4);
      return tagOpenAttributeNameAfter;
    }
    return tagOpenBetween(code4);
  }
  function tagOpenAttributeValueBefore(code4) {
    if (code4 === null || code4 === 60 || code4 === 61 || code4 === 62 || code4 === 96) {
      return nok(code4);
    }
    if (code4 === 34 || code4 === 39) {
      effects.consume(code4);
      marker = code4;
      return tagOpenAttributeValueQuoted;
    }
    if (markdownLineEnding(code4)) {
      returnState = tagOpenAttributeValueBefore;
      return lineEndingBefore(code4);
    }
    if (markdownSpace(code4)) {
      effects.consume(code4);
      return tagOpenAttributeValueBefore;
    }
    effects.consume(code4);
    return tagOpenAttributeValueUnquoted;
  }
  function tagOpenAttributeValueQuoted(code4) {
    if (code4 === marker) {
      effects.consume(code4);
      marker = void 0;
      return tagOpenAttributeValueQuotedAfter;
    }
    if (code4 === null) {
      return nok(code4);
    }
    if (markdownLineEnding(code4)) {
      returnState = tagOpenAttributeValueQuoted;
      return lineEndingBefore(code4);
    }
    effects.consume(code4);
    return tagOpenAttributeValueQuoted;
  }
  function tagOpenAttributeValueUnquoted(code4) {
    if (code4 === null || code4 === 34 || code4 === 39 || code4 === 60 || code4 === 61 || code4 === 96) {
      return nok(code4);
    }
    if (code4 === 47 || code4 === 62 || markdownLineEndingOrSpace(code4)) {
      return tagOpenBetween(code4);
    }
    effects.consume(code4);
    return tagOpenAttributeValueUnquoted;
  }
  function tagOpenAttributeValueQuotedAfter(code4) {
    if (code4 === 47 || code4 === 62 || markdownLineEndingOrSpace(code4)) {
      return tagOpenBetween(code4);
    }
    return nok(code4);
  }
  function end(code4) {
    if (code4 === 62) {
      effects.consume(code4);
      effects.exit("htmlTextData");
      effects.exit("htmlText");
      return ok2;
    }
    return nok(code4);
  }
  function lineEndingBefore(code4) {
    effects.exit("htmlTextData");
    effects.enter("lineEnding");
    effects.consume(code4);
    effects.exit("lineEnding");
    return lineEndingAfter;
  }
  function lineEndingAfter(code4) {
    return markdownSpace(code4) ? factorySpace(effects, lineEndingAfterPrefix, "linePrefix", self.parser.constructs.disable.null.includes("codeIndented") ? void 0 : 4)(code4) : lineEndingAfterPrefix(code4);
  }
  function lineEndingAfterPrefix(code4) {
    effects.enter("htmlTextData");
    return returnState(code4);
  }
}

// node_modules/.pnpm/micromark-core-commonmark@2.0.4/node_modules/micromark-core-commonmark/lib/label-end.js
var labelEnd = {
  name: "labelEnd",
  resolveAll: resolveAllLabelEnd,
  resolveTo: resolveToLabelEnd,
  tokenize: tokenizeLabelEnd
};
var resourceConstruct = {
  tokenize: tokenizeResource
};
var referenceFullConstruct = {
  tokenize: tokenizeReferenceFull
};
var referenceCollapsedConstruct = {
  tokenize: tokenizeReferenceCollapsed
};
function resolveAllLabelEnd(events) {
  let index2 = -1;
  const newEvents = [];
  while (++index2 < events.length) {
    const token = events[index2][1];
    newEvents.push(events[index2]);
    if (token.type === "labelImage" || token.type === "labelLink" || token.type === "labelEnd") {
      const offset = token.type === "labelImage" ? 4 : 2;
      token.type = "data";
      index2 += offset;
    }
  }
  if (events.length !== newEvents.length) {
    splice(events, 0, events.length, newEvents);
  }
  return events;
}
function resolveToLabelEnd(events, context) {
  let index2 = events.length;
  let offset = 0;
  let open;
  let close2;
  let media;
  while (index2--) {
    const token = events[index2][1];
    if (open) {
      if (token.type === "link" || token.type === "labelLink" && token._inactive) {
        break;
      }
      if (events[index2][0] === "enter" && token.type === "labelLink") {
        token._inactive = true;
      }
    } else if (close2) {
      if (events[index2][0] === "enter" && (token.type === "labelImage" || token.type === "labelLink") && !token._balanced) {
        open = index2;
        if (token.type !== "labelLink") {
          offset = 2;
          break;
        }
      }
    } else if (token.type === "labelEnd") {
      close2 = index2;
    }
  }
  const group = {
    type: events[open][1].type === "labelLink" ? "link" : "image",
    start: {
      ...events[open][1].start
    },
    end: {
      ...events[events.length - 1][1].end
    }
  };
  const label = {
    type: "label",
    start: {
      ...events[open][1].start
    },
    end: {
      ...events[close2][1].end
    }
  };
  const text4 = {
    type: "labelText",
    start: {
      ...events[open + offset + 2][1].end
    },
    end: {
      ...events[close2 - 2][1].start
    }
  };
  media = [["enter", group, context], ["enter", label, context]];
  media = push(media, events.slice(open + 1, open + offset + 3));
  media = push(media, [["enter", text4, context]]);
  media = push(media, resolveAll(context.parser.constructs.insideSpan.null, events.slice(open + offset + 4, close2 - 3), context));
  media = push(media, [["exit", text4, context], events[close2 - 2], events[close2 - 1], ["exit", label, context]]);
  media = push(media, events.slice(close2 + 1));
  media = push(media, [["exit", group, context]]);
  splice(events, open, events.length, media);
  return events;
}
function tokenizeLabelEnd(effects, ok2, nok) {
  const self = this;
  const labelStarts = self._labelStarts;
  let labelStart;
  let defined;
  if (labelStarts) {
    while (labelStarts.length > 0 && labelStarts[labelStarts.length - 1]._balanced) {
      labelStarts.pop();
    }
    labelStart = labelStarts[labelStarts.length - 1];
  }
  return start;
  function start(code4) {
    if (!labelStart) {
      return nok(code4);
    }
    if (labelStart._inactive) {
      return labelEndNok(code4);
    }
    defined = self.parser.defined.includes(normalizeIdentifier(self.sliceSerialize({
      start: labelStart.end,
      end: self.now()
    })));
    effects.enter("labelEnd");
    effects.enter("labelMarker");
    effects.consume(code4);
    effects.exit("labelMarker");
    effects.exit("labelEnd");
    return after;
  }
  function after(code4) {
    if (code4 === 40) {
      return effects.attempt(resourceConstruct, labelEndOk, defined ? labelEndOk : labelEndNok)(code4);
    }
    if (code4 === 91) {
      return effects.attempt(referenceFullConstruct, labelEndOk, defined ? referenceNotFull : labelEndNok)(code4);
    }
    return defined ? labelEndOk(code4) : labelEndNok(code4);
  }
  function referenceNotFull(code4) {
    return effects.attempt(referenceCollapsedConstruct, labelEndOk, labelEndNok)(code4);
  }
  function labelEndOk(code4) {
    labelStarts.pop();
    return ok2(code4);
  }
  function labelEndNok(code4) {
    labelStart._balanced = true;
    return nok(code4);
  }
}
function tokenizeResource(effects, ok2, nok) {
  return resourceStart;
  function resourceStart(code4) {
    effects.enter("resource");
    effects.enter("resourceMarker");
    effects.consume(code4);
    effects.exit("resourceMarker");
    return resourceBefore;
  }
  function resourceBefore(code4) {
    return markdownLineEndingOrSpace(code4) ? factoryWhitespace(effects, resourceOpen)(code4) : resourceOpen(code4);
  }
  function resourceOpen(code4) {
    if (code4 === 41) {
      return resourceEnd(code4);
    }
    return factoryDestination(effects, resourceDestinationAfter, resourceDestinationMissing, "resourceDestination", "resourceDestinationLiteral", "resourceDestinationLiteralMarker", "resourceDestinationRaw", "resourceDestinationString", 32)(code4);
  }
  function resourceDestinationAfter(code4) {
    return markdownLineEndingOrSpace(code4) ? factoryWhitespace(effects, resourceBetween)(code4) : resourceEnd(code4);
  }
  function resourceDestinationMissing(code4) {
    return nok(code4);
  }
  function resourceBetween(code4) {
    if (code4 === 34 || code4 === 39 || code4 === 40) {
      return factoryTitle(effects, resourceTitleAfter, nok, "resourceTitle", "resourceTitleMarker", "resourceTitleString")(code4);
    }
    return resourceEnd(code4);
  }
  function resourceTitleAfter(code4) {
    return markdownLineEndingOrSpace(code4) ? factoryWhitespace(effects, resourceEnd)(code4) : resourceEnd(code4);
  }
  function resourceEnd(code4) {
    if (code4 === 41) {
      effects.enter("resourceMarker");
      effects.consume(code4);
      effects.exit("resourceMarker");
      effects.exit("resource");
      return ok2;
    }
    return nok(code4);
  }
}
function tokenizeReferenceFull(effects, ok2, nok) {
  const self = this;
  return referenceFull;
  function referenceFull(code4) {
    return factoryLabel.call(self, effects, referenceFullAfter, referenceFullMissing, "reference", "referenceMarker", "referenceString")(code4);
  }
  function referenceFullAfter(code4) {
    return self.parser.defined.includes(normalizeIdentifier(self.sliceSerialize(self.events[self.events.length - 1][1]).slice(1, -1))) ? ok2(code4) : nok(code4);
  }
  function referenceFullMissing(code4) {
    return nok(code4);
  }
}
function tokenizeReferenceCollapsed(effects, ok2, nok) {
  return referenceCollapsedStart;
  function referenceCollapsedStart(code4) {
    effects.enter("reference");
    effects.enter("referenceMarker");
    effects.consume(code4);
    effects.exit("referenceMarker");
    return referenceCollapsedOpen;
  }
  function referenceCollapsedOpen(code4) {
    if (code4 === 93) {
      effects.enter("referenceMarker");
      effects.consume(code4);
      effects.exit("referenceMarker");
      effects.exit("reference");
      return ok2;
    }
    return nok(code4);
  }
}

// node_modules/.pnpm/micromark-core-commonmark@2.0.4/node_modules/micromark-core-commonmark/lib/label-start-image.js
var labelStartImage = {
  name: "labelStartImage",
  resolveAll: labelEnd.resolveAll,
  tokenize: tokenizeLabelStartImage
};
function tokenizeLabelStartImage(effects, ok2, nok) {
  const self = this;
  let labelImage;
  return start;
  function start(code4) {
    effects.enter("labelImage");
    effects.enter("labelImageMarker");
    effects.consume(code4);
    effects.exit("labelImageMarker");
    return open;
  }
  function open(code4) {
    if (code4 === 91) {
      effects.enter("labelMarker");
      effects.consume(code4);
      effects.exit("labelMarker");
      labelImage = effects.exit("labelImage");
      return after;
    }
    return nok(code4);
  }
  function after(code4) {
    if (code4 === 94 && "_hiddenFootnoteSupport" in self.parser.constructs) {
      return nok(code4);
    }
    self._labelStarts = self._labelStarts || [];
    self._labelStarts.push(labelImage);
    return ok2(code4);
  }
}

// node_modules/.pnpm/micromark-core-commonmark@2.0.4/node_modules/micromark-core-commonmark/lib/label-start-link.js
var labelStartLink = {
  name: "labelStartLink",
  resolveAll: labelEnd.resolveAll,
  tokenize: tokenizeLabelStartLink
};
function tokenizeLabelStartLink(effects, ok2, nok) {
  const self = this;
  let labelLink;
  return start;
  function start(code4) {
    effects.enter("labelLink");
    effects.enter("labelMarker");
    effects.consume(code4);
    effects.exit("labelMarker");
    labelLink = effects.exit("labelLink");
    return after;
  }
  function after(code4) {
    if (code4 === 94 && "_hiddenFootnoteSupport" in self.parser.constructs) {
      return nok(code4);
    }
    self._labelStarts = self._labelStarts || [];
    self._labelStarts.push(labelLink);
    return ok2(code4);
  }
}

// node_modules/.pnpm/micromark-core-commonmark@2.0.4/node_modules/micromark-core-commonmark/lib/line-ending.js
var lineEnding = {
  name: "lineEnding",
  tokenize: tokenizeLineEnding
};
function tokenizeLineEnding(effects, ok2) {
  return start;
  function start(code4) {
    effects.enter("lineEnding");
    effects.consume(code4);
    effects.exit("lineEnding");
    return factorySpace(effects, ok2, "linePrefix");
  }
}

// node_modules/.pnpm/micromark-core-commonmark@2.0.4/node_modules/micromark-core-commonmark/lib/thematic-break.js
var thematicBreak = {
  name: "thematicBreak",
  tokenize: tokenizeThematicBreak
};
function tokenizeThematicBreak(effects, ok2, nok) {
  let size = 0;
  let marker;
  return start;
  function start(code4) {
    effects.enter("thematicBreak");
    return before(code4);
  }
  function before(code4) {
    marker = code4;
    return atBreak(code4);
  }
  function atBreak(code4) {
    if (code4 === marker) {
      effects.enter("thematicBreakSequence");
      return sequence(code4);
    }
    if (size >= 3 && (code4 === null || markdownLineEnding(code4))) {
      effects.exit("thematicBreak");
      return ok2(code4);
    }
    return nok(code4);
  }
  function sequence(code4) {
    if (code4 === marker) {
      effects.consume(code4);
      size++;
      return sequence;
    }
    effects.exit("thematicBreakSequence");
    return markdownSpace(code4) ? factorySpace(effects, atBreak, "whitespace")(code4) : atBreak(code4);
  }
}

// node_modules/.pnpm/micromark-core-commonmark@2.0.4/node_modules/micromark-core-commonmark/lib/list.js
var list = {
  continuation: {
    tokenize: tokenizeListContinuation
  },
  exit: tokenizeListEnd,
  name: "list",
  tokenize: tokenizeListStart
};
var listItemPrefixWhitespaceConstruct = {
  partial: true,
  tokenize: tokenizeListItemPrefixWhitespace
};
var indentConstruct = {
  partial: true,
  tokenize: tokenizeIndent
};
function tokenizeListStart(effects, ok2, nok) {
  const self = this;
  const tail = self.events[self.events.length - 1];
  let initialSize = tail && tail[1].type === "linePrefix" ? tail[2].sliceSerialize(tail[1], true).length : 0;
  let size = 0;
  return start;
  function start(code4) {
    const kind = self.containerState.type || (code4 === 42 || code4 === 43 || code4 === 45 ? "listUnordered" : "listOrdered");
    if (kind === "listUnordered" ? !self.containerState.marker || code4 === self.containerState.marker : asciiDigit(code4)) {
      if (!self.containerState.type) {
        self.containerState.type = kind;
        effects.enter(kind, {
          _container: true
        });
      }
      if (kind === "listUnordered") {
        effects.enter("listItemPrefix");
        return code4 === 42 || code4 === 45 ? effects.check(thematicBreak, nok, atMarker)(code4) : atMarker(code4);
      }
      if (!self.interrupt || code4 === 49) {
        effects.enter("listItemPrefix");
        effects.enter("listItemValue");
        return inside(code4);
      }
    }
    return nok(code4);
  }
  function inside(code4) {
    if (asciiDigit(code4) && ++size < 10) {
      effects.consume(code4);
      return inside;
    }
    if ((!self.interrupt || size < 2) && (self.containerState.marker ? code4 === self.containerState.marker : code4 === 41 || code4 === 46)) {
      effects.exit("listItemValue");
      return atMarker(code4);
    }
    return nok(code4);
  }
  function atMarker(code4) {
    effects.enter("listItemMarker");
    effects.consume(code4);
    effects.exit("listItemMarker");
    self.containerState.marker = self.containerState.marker || code4;
    return effects.check(
      blankLine,
      // Can’t be empty when interrupting.
      self.interrupt ? nok : onBlank,
      effects.attempt(listItemPrefixWhitespaceConstruct, endOfPrefix, otherPrefix)
    );
  }
  function onBlank(code4) {
    self.containerState.initialBlankLine = true;
    initialSize++;
    return endOfPrefix(code4);
  }
  function otherPrefix(code4) {
    if (markdownSpace(code4)) {
      effects.enter("listItemPrefixWhitespace");
      effects.consume(code4);
      effects.exit("listItemPrefixWhitespace");
      return endOfPrefix;
    }
    return nok(code4);
  }
  function endOfPrefix(code4) {
    self.containerState.size = initialSize + self.sliceSerialize(effects.exit("listItemPrefix"), true).length;
    return ok2(code4);
  }
}
function tokenizeListContinuation(effects, ok2, nok) {
  const self = this;
  self.containerState._closeFlow = void 0;
  return effects.check(blankLine, onBlank, notBlank);
  function onBlank(code4) {
    self.containerState.furtherBlankLines = self.containerState.furtherBlankLines || self.containerState.initialBlankLine;
    return factorySpace(effects, ok2, "listItemIndent", self.containerState.size + 1)(code4);
  }
  function notBlank(code4) {
    if (self.containerState.furtherBlankLines || !markdownSpace(code4)) {
      self.containerState.furtherBlankLines = void 0;
      self.containerState.initialBlankLine = void 0;
      return notInCurrentItem(code4);
    }
    self.containerState.furtherBlankLines = void 0;
    self.containerState.initialBlankLine = void 0;
    return effects.attempt(indentConstruct, ok2, notInCurrentItem)(code4);
  }
  function notInCurrentItem(code4) {
    self.containerState._closeFlow = true;
    self.interrupt = void 0;
    return factorySpace(effects, effects.attempt(list, ok2, nok), "linePrefix", self.parser.constructs.disable.null.includes("codeIndented") ? void 0 : 4)(code4);
  }
}
function tokenizeIndent(effects, ok2, nok) {
  const self = this;
  return factorySpace(effects, afterPrefix, "listItemIndent", self.containerState.size + 1);
  function afterPrefix(code4) {
    const tail = self.events[self.events.length - 1];
    return tail && tail[1].type === "listItemIndent" && tail[2].sliceSerialize(tail[1], true).length === self.containerState.size ? ok2(code4) : nok(code4);
  }
}
function tokenizeListEnd(effects) {
  effects.exit(this.containerState.type);
}
function tokenizeListItemPrefixWhitespace(effects, ok2, nok) {
  const self = this;
  return factorySpace(effects, afterPrefix, "listItemPrefixWhitespace", self.parser.constructs.disable.null.includes("codeIndented") ? void 0 : 4 + 1);
  function afterPrefix(code4) {
    const tail = self.events[self.events.length - 1];
    return !markdownSpace(code4) && tail && tail[1].type === "listItemPrefixWhitespace" ? ok2(code4) : nok(code4);
  }
}

// node_modules/.pnpm/micromark-core-commonmark@2.0.4/node_modules/micromark-core-commonmark/lib/setext-underline.js
var setextUnderline = {
  name: "setextUnderline",
  resolveTo: resolveToSetextUnderline,
  tokenize: tokenizeSetextUnderline
};
function resolveToSetextUnderline(events, context) {
  const editMap = new EditMap();
  let index2 = events.length;
  let content3;
  let text4;
  let definition3;
  while (index2--) {
    if (events[index2][0] === "enter") {
      if (events[index2][1].type === "content") {
        content3 = index2;
        break;
      }
      if (events[index2][1].type === "paragraph") {
        text4 = index2;
      }
    } else {
      if (events[index2][1].type === "content") {
        editMap.add(index2, 1, []);
      }
      if (!definition3 && events[index2][1].type === "definition") {
        definition3 = index2;
      }
    }
  }
  const heading2 = {
    type: "setextHeading",
    start: {
      ...events[content3][1].start
    },
    end: {
      ...events[events.length - 1][1].end
    }
  };
  events[text4][1].type = "setextHeadingText";
  if (definition3) {
    editMap.add(text4, 0, [["enter", heading2, context]]);
    editMap.add(definition3 + 1, 0, [["exit", events[content3][1], context]]);
    events[content3][1].end = {
      ...events[definition3][1].end
    };
  } else {
    events[content3][1] = heading2;
  }
  editMap.add(events.length, 0, [["exit", heading2, context]]);
  editMap.consume(events);
  return events;
}
function tokenizeSetextUnderline(effects, ok2, nok) {
  const self = this;
  let marker;
  return start;
  function start(code4) {
    let index2 = self.events.length;
    let paragraph2;
    while (index2--) {
      if (self.events[index2][1].type !== "lineEnding" && self.events[index2][1].type !== "linePrefix" && self.events[index2][1].type !== "content") {
        paragraph2 = self.events[index2][1].type === "paragraph";
        break;
      }
    }
    if (!self.parser.lazy[self.now().line] && (self.interrupt || paragraph2)) {
      effects.enter("setextHeadingLine");
      marker = code4;
      return before(code4);
    }
    return nok(code4);
  }
  function before(code4) {
    effects.enter("setextHeadingLineSequence");
    return inside(code4);
  }
  function inside(code4) {
    if (code4 === marker) {
      effects.consume(code4);
      return inside;
    }
    effects.exit("setextHeadingLineSequence");
    return markdownSpace(code4) ? factorySpace(effects, after, "lineSuffix")(code4) : after(code4);
  }
  function after(code4) {
    if (code4 === null || markdownLineEnding(code4)) {
      effects.exit("setextHeadingLine");
      return ok2(code4);
    }
    return nok(code4);
  }
}

// node_modules/.pnpm/micromark@4.0.3/node_modules/micromark/lib/initialize/flow.js
var flow = {
  tokenize: initializeFlow
};
function initializeFlow(effects) {
  const self = this;
  const initial = effects.attempt(
    // Try to parse a blank line.
    blankLine,
    atBlankEnding,
    // Try to parse initial flow (essentially, only code).
    effects.attempt(this.parser.constructs.flowInitial, afterConstruct, factorySpace(effects, effects.attempt(this.parser.constructs.flow, afterConstruct, effects.attempt(content2, afterConstruct)), "linePrefix"))
  );
  return initial;
  function atBlankEnding(code4) {
    if (code4 === null) {
      effects.consume(code4);
      return;
    }
    effects.enter("lineEndingBlank");
    effects.consume(code4);
    effects.exit("lineEndingBlank");
    self.currentConstruct = void 0;
    return initial;
  }
  function afterConstruct(code4) {
    if (code4 === null) {
      effects.consume(code4);
      return;
    }
    effects.enter("lineEnding");
    effects.consume(code4);
    effects.exit("lineEnding");
    self.currentConstruct = void 0;
    return initial;
  }
}

// node_modules/.pnpm/micromark@4.0.3/node_modules/micromark/lib/initialize/text.js
var resolver = {
  resolveAll: createResolver()
};
var string = initializeFactory("string");
var text = initializeFactory("text");
function initializeFactory(field) {
  return {
    resolveAll: createResolver(field === "text" ? resolveAllLineSuffixes : void 0),
    tokenize: initializeText
  };
  function initializeText(effects) {
    const self = this;
    const constructs2 = this.parser.constructs[field];
    const text4 = effects.attempt(constructs2, start, notText);
    return start;
    function start(code4) {
      return atBreak(code4) ? text4(code4) : notText(code4);
    }
    function notText(code4) {
      if (code4 === null) {
        effects.consume(code4);
        return;
      }
      effects.enter("data");
      effects.consume(code4);
      return data;
    }
    function data(code4) {
      if (atBreak(code4)) {
        effects.exit("data");
        return text4(code4);
      }
      effects.consume(code4);
      return data;
    }
    function atBreak(code4) {
      if (code4 === null) {
        return true;
      }
      const list4 = constructs2[code4];
      let index2 = -1;
      if (list4) {
        while (++index2 < list4.length) {
          const item = list4[index2];
          if (!item.previous || item.previous.call(self, self.previous)) {
            return true;
          }
        }
      }
      return false;
    }
  }
}
function createResolver(extraResolver) {
  return resolveAllText;
  function resolveAllText(events, context) {
    let index2 = -1;
    let enter;
    while (++index2 <= events.length) {
      if (enter === void 0) {
        if (events[index2] && events[index2][1].type === "data") {
          enter = index2;
          index2++;
        }
      } else if (!events[index2] || events[index2][1].type !== "data") {
        if (index2 !== enter + 2) {
          events[enter][1].end = events[index2 - 1][1].end;
          events.splice(enter + 2, index2 - enter - 2);
          index2 = enter + 2;
        }
        enter = void 0;
      }
    }
    return extraResolver ? extraResolver(events, context) : events;
  }
}
function resolveAllLineSuffixes(events, context) {
  const editMap = new EditMap();
  let eventIndex = 0;
  while (++eventIndex <= events.length) {
    if ((eventIndex === events.length || events[eventIndex][1].type === "lineEnding") && events[eventIndex - 1][1].type === "data") {
      const data = events[eventIndex - 1][1];
      const chunks = context.sliceStream(data);
      let index2 = chunks.length;
      let bufferIndex = -1;
      let size = 0;
      let tabs;
      while (index2--) {
        const chunk = chunks[index2];
        if (typeof chunk === "string") {
          bufferIndex = chunk.length;
          while (chunk.charCodeAt(bufferIndex - 1) === 32) {
            size++;
            bufferIndex--;
          }
          if (bufferIndex) {
            break;
          }
          bufferIndex = -1;
        } else if (chunk === -2) {
          tabs = true;
          size++;
        } else if (chunk === -1) {
        } else {
          index2++;
          break;
        }
      }
      if (context._contentTypeTextTrailing && eventIndex === events.length) {
        size = 0;
      }
      if (size) {
        const token = {
          type: eventIndex === events.length || tabs || size < 2 ? "lineSuffix" : "hardBreakTrailing",
          start: {
            _bufferIndex: index2 ? bufferIndex : data.start._bufferIndex + bufferIndex,
            _index: data.start._index + index2,
            line: data.end.line,
            column: data.end.column - size,
            offset: data.end.offset - size
          },
          end: {
            ...data.end
          }
        };
        data.end = {
          ...token.start
        };
        if (data.start.offset === data.end.offset) {
          Object.assign(data, token);
        } else {
          editMap.add(eventIndex, 0, [["enter", token, context], ["exit", token, context]]);
        }
      }
      eventIndex++;
    }
  }
  editMap.consume(events);
  return events;
}

// node_modules/.pnpm/micromark@4.0.3/node_modules/micromark/lib/constructs.js
var constructs_exports = {};
__export(constructs_exports, {
  attentionMarkers: () => attentionMarkers,
  contentInitial: () => contentInitial,
  disable: () => disable,
  document: () => document3,
  flow: () => flow2,
  flowInitial: () => flowInitial,
  insideSpan: () => insideSpan,
  string: () => string2,
  text: () => text2
});
var document3 = {
  [42]: list,
  [43]: list,
  [45]: list,
  [48]: list,
  [49]: list,
  [50]: list,
  [51]: list,
  [52]: list,
  [53]: list,
  [54]: list,
  [55]: list,
  [56]: list,
  [57]: list,
  [62]: blockQuote
};
var contentInitial = {
  [91]: definition
};
var flowInitial = {
  [-2]: codeIndented,
  [-1]: codeIndented,
  [32]: codeIndented
};
var flow2 = {
  [35]: headingAtx,
  [42]: thematicBreak,
  [45]: [setextUnderline, thematicBreak],
  [60]: htmlFlow,
  [61]: setextUnderline,
  [95]: thematicBreak,
  [96]: codeFenced,
  [126]: codeFenced
};
var string2 = {
  [38]: characterReference,
  [92]: characterEscape
};
var text2 = {
  [-5]: lineEnding,
  [-4]: lineEnding,
  [-3]: lineEnding,
  [33]: labelStartImage,
  [38]: characterReference,
  [42]: attention,
  [60]: [autolink, htmlText],
  [91]: labelStartLink,
  [92]: [hardBreakEscape, characterEscape],
  [93]: labelEnd,
  [95]: attention,
  [96]: codeText
};
var insideSpan = {
  null: [attention, resolver]
};
var attentionMarkers = {
  null: [42, 95]
};
var disable = {
  null: []
};

// node_modules/.pnpm/micromark@4.0.3/node_modules/micromark/lib/create-tokenizer.js
function createTokenizer(parser, initialize, from2) {
  let point3 = {
    _bufferIndex: -1,
    _index: 0,
    line: from2 && from2.line || 1,
    column: from2 && from2.column || 1,
    offset: from2 && from2.offset || 0
  };
  const columnStart = {};
  const resolveAllConstructs = [];
  let chunks = [];
  let stack = [];
  let consumed = true;
  const effects = {
    attempt: constructFactory(onsuccessfulconstruct),
    check: constructFactory(onsuccessfulcheck),
    consume,
    enter,
    exit: exit2,
    interrupt: constructFactory(onsuccessfulcheck, {
      interrupt: true
    })
  };
  const context = {
    code: null,
    containerState: {},
    defineSkip,
    events: [],
    now,
    parser,
    previous: null,
    sliceSerialize,
    sliceStream,
    write
  };
  let state = initialize.tokenize.call(context, effects);
  let expectedCode;
  if (initialize.resolveAll) {
    resolveAllConstructs.push(initialize);
  }
  return context;
  function write(slice2) {
    chunks = push(chunks, slice2);
    main();
    if (chunks[chunks.length - 1] !== null) {
      return [];
    }
    addResult(initialize, 0);
    context.events = resolveAll(resolveAllConstructs, context.events, context);
    return context.events;
  }
  function sliceSerialize(token, expandTabs) {
    return serializeChunks(sliceStream(token), expandTabs);
  }
  function sliceStream(token) {
    return sliceChunks(chunks, token);
  }
  function now() {
    const {
      _bufferIndex,
      _index,
      line,
      column,
      offset
    } = point3;
    return {
      _bufferIndex,
      _index,
      line,
      column,
      offset
    };
  }
  function defineSkip(value) {
    columnStart[value.line] = value.column;
    accountForPotentialSkip();
  }
  function main() {
    while (point3._index < chunks.length) {
      const chunk = chunks[point3._index];
      if (typeof chunk === "string") {
        const chunkIndex = point3._index;
        if (point3._bufferIndex < 0) {
          point3._bufferIndex = 0;
        }
        while (point3._index === chunkIndex && point3._bufferIndex < chunk.length) {
          go(chunk.charCodeAt(point3._bufferIndex));
        }
      } else {
        go(chunk);
      }
    }
  }
  function go(code4) {
    consumed = void 0;
    expectedCode = code4;
    state = state(code4);
  }
  function consume(code4) {
    if (markdownLineEnding(code4)) {
      point3.line++;
      point3.column = 1;
      point3.offset += code4 === -3 ? 2 : 1;
      accountForPotentialSkip();
    } else if (code4 !== -1) {
      point3.column++;
      point3.offset++;
    }
    if (point3._bufferIndex < 0) {
      point3._index++;
    } else {
      point3._bufferIndex++;
      if (point3._bufferIndex === // Points w/ non-negative `_bufferIndex` reference
      // strings.
      /** @type {string} */
      chunks[point3._index].length) {
        point3._bufferIndex = -1;
        point3._index++;
      }
    }
    context.previous = code4;
    consumed = true;
  }
  function enter(type, fields) {
    const token = fields || {};
    token.type = type;
    token.start = now();
    context.events.push(["enter", token, context]);
    stack.push(token);
    return token;
  }
  function exit2(type) {
    const token = stack.pop();
    token.end = now();
    context.events.push(["exit", token, context]);
    return token;
  }
  function onsuccessfulconstruct(construct, info) {
    addResult(construct, info.from);
  }
  function onsuccessfulcheck(_, info) {
    info.restore();
  }
  function constructFactory(onreturn, fields) {
    return hook;
    function hook(constructs2, returnState, bogusState) {
      let listOfConstructs;
      let constructIndex;
      let currentConstruct;
      let info;
      return Array.isArray(constructs2) ? (
        /* c8 ignore next 1 */
        handleListOfConstructs(constructs2)
      ) : "tokenize" in constructs2 ? (
        // Looks like a construct.
        handleListOfConstructs([
          /** @type {Construct} */
          constructs2
        ])
      ) : handleMapOfConstructs(constructs2);
      function handleMapOfConstructs(map5) {
        return start;
        function start(code4) {
          const left = code4 !== null && map5[code4];
          const all2 = code4 !== null && map5.null;
          const list4 = [
            // To do: add more extension tests.
            /* c8 ignore next 2 */
            ...Array.isArray(left) ? left : left ? [left] : [],
            ...Array.isArray(all2) ? all2 : all2 ? [all2] : []
          ];
          return handleListOfConstructs(list4)(code4);
        }
      }
      function handleListOfConstructs(list4) {
        listOfConstructs = list4;
        constructIndex = 0;
        if (list4.length === 0) {
          return bogusState;
        }
        return handleConstruct(list4[constructIndex]);
      }
      function handleConstruct(construct) {
        return start;
        function start(code4) {
          info = store();
          currentConstruct = construct;
          if (!construct.partial) {
            context.currentConstruct = construct;
          }
          if (construct.name && context.parser.constructs.disable.null.includes(construct.name)) {
            return nok(code4);
          }
          return construct.tokenize.call(
            // If we do have fields, create an object w/ `context` as its
            // prototype.
            // This allows a “live binding”, which is needed for `interrupt`.
            fields ? Object.assign(Object.create(context), fields) : context,
            effects,
            ok2,
            nok
          )(code4);
        }
      }
      function ok2(code4) {
        consumed = true;
        onreturn(currentConstruct, info);
        return returnState;
      }
      function nok(code4) {
        consumed = true;
        info.restore();
        if (++constructIndex < listOfConstructs.length) {
          return handleConstruct(listOfConstructs[constructIndex]);
        }
        return bogusState;
      }
    }
  }
  function addResult(construct, from3) {
    if (construct.resolveAll && !resolveAllConstructs.includes(construct)) {
      resolveAllConstructs.push(construct);
    }
    if (construct.resolve) {
      splice(context.events, from3, context.events.length - from3, construct.resolve(context.events.slice(from3), context));
    }
    if (construct.resolveTo) {
      context.events = construct.resolveTo(context.events, context);
    }
  }
  function store() {
    const startPoint = now();
    const startPrevious = context.previous;
    const startCurrentConstruct = context.currentConstruct;
    const startEventsIndex = context.events.length;
    const startStack = Array.from(stack);
    return {
      from: startEventsIndex,
      restore
    };
    function restore() {
      point3 = startPoint;
      context.previous = startPrevious;
      context.currentConstruct = startCurrentConstruct;
      context.events.length = startEventsIndex;
      stack = startStack;
      accountForPotentialSkip();
    }
  }
  function accountForPotentialSkip() {
    if (point3.line in columnStart && point3.column < 2) {
      point3.column = columnStart[point3.line];
      point3.offset += columnStart[point3.line] - 1;
    }
  }
}
function sliceChunks(chunks, token) {
  const startIndex = token.start._index;
  const startBufferIndex = token.start._bufferIndex;
  const endIndex = token.end._index;
  const endBufferIndex = token.end._bufferIndex;
  let view;
  if (startIndex === endIndex) {
    view = [chunks[startIndex].slice(startBufferIndex, endBufferIndex)];
  } else {
    view = chunks.slice(startIndex, endIndex);
    if (startBufferIndex > -1) {
      const head = view[0];
      if (typeof head === "string") {
        view[0] = head.slice(startBufferIndex);
      } else {
        view.shift();
      }
    }
    if (endBufferIndex > 0) {
      view.push(chunks[endIndex].slice(0, endBufferIndex));
    }
  }
  return view;
}
function serializeChunks(chunks, expandTabs) {
  let index2 = -1;
  const result = [];
  let atTab;
  while (++index2 < chunks.length) {
    const chunk = chunks[index2];
    let value;
    if (typeof chunk === "string") {
      value = chunk;
    } else {
      switch (chunk) {
        case -5: {
          value = "\r";
          break;
        }
        case -4: {
          value = "\n";
          break;
        }
        case -3: {
          value = "\r\n";
          break;
        }
        case -2: {
          value = expandTabs ? " " : "	";
          break;
        }
        case -1: {
          if (!expandTabs && atTab) {
            continue;
          }
          value = " ";
          break;
        }
        default: {
          value = String.fromCharCode(chunk);
        }
      }
    }
    atTab = chunk === -2;
    result.push(value);
  }
  return result.join("");
}

// node_modules/.pnpm/micromark@4.0.3/node_modules/micromark/lib/parse.js
function parse(options) {
  const settings = options || {};
  const constructs2 = (
    /** @type {FullNormalizedExtension} */
    combineExtensions([constructs_exports, ...settings.extensions || []])
  );
  const parser = {
    constructs: constructs2,
    content: create(content),
    defined: [],
    document: create(document2),
    flow: create(flow),
    lazy: {},
    string: create(string),
    text: create(text)
  };
  return parser;
  function create(initial) {
    return creator;
    function creator(from2) {
      return createTokenizer(parser, initial, from2);
    }
  }
}

// node_modules/.pnpm/micromark@4.0.3/node_modules/micromark/lib/postprocess.js
function postprocess(events) {
  while (!subtokenize(events)) {
  }
  return events;
}

// node_modules/.pnpm/micromark@4.0.3/node_modules/micromark/lib/preprocess.js
var search = /[\0\t\n\r]/g;
function preprocess() {
  let column = 1;
  let buffer = "";
  let start = true;
  let atCarriageReturn;
  return preprocessor;
  function preprocessor(value, encoding, end) {
    value = buffer + (typeof value === "string" ? value.toString() : new TextDecoder(encoding || void 0).decode(value));
    const chunks = [];
    let startPosition = 0;
    buffer = "";
    if (start) {
      if (value.charCodeAt(0) === 65279) {
        startPosition++;
      }
      start = void 0;
    }
    while (startPosition < value.length) {
      search.lastIndex = startPosition;
      const match = search.exec(value);
      const endPosition = match && match.index !== void 0 ? match.index : value.length;
      const code4 = value.charCodeAt(endPosition);
      if (!match) {
        buffer = value.slice(startPosition);
        break;
      }
      if (code4 === 10 && startPosition === endPosition && atCarriageReturn) {
        chunks.push(-3);
        atCarriageReturn = void 0;
      } else {
        if (atCarriageReturn) {
          chunks.push(-5);
          atCarriageReturn = void 0;
        }
        if (startPosition < endPosition) {
          chunks.push(value.slice(startPosition, endPosition));
          column += endPosition - startPosition;
        }
        switch (code4) {
          case 0: {
            chunks.push(65533);
            column++;
            break;
          }
          case 9: {
            const next = Math.ceil(column / 4) * 4;
            chunks.push(-2);
            while (column++ < next) {
              chunks.push(-1);
            }
            break;
          }
          case 10: {
            chunks.push(-4);
            column = 1;
            break;
          }
          default: {
            atCarriageReturn = true;
            column = 1;
          }
        }
      }
      startPosition = endPosition + 1;
    }
    if (end) {
      if (atCarriageReturn) {
        chunks.push(-5);
      }
      if (buffer) {
        chunks.push(buffer);
      }
      chunks.push(null);
    }
    return chunks;
  }
}

// node_modules/.pnpm/micromark-util-decode-string@2.0.1/node_modules/micromark-util-decode-string/index.js
var characterEscapeOrReference = /\\([!-/:-@[-`{-~])|&(#(?:\d{1,7}|x[\da-f]{1,6})|[\da-z]{1,31});/gi;
function decodeString(value) {
  return value.replace(characterEscapeOrReference, decode);
}
function decode($0, $1, $2) {
  if ($1) {
    return $1;
  }
  const head = $2.charCodeAt(0);
  if (head === 35) {
    const head2 = $2.charCodeAt(1);
    const hex = head2 === 120 || head2 === 88;
    return decodeNumericCharacterReference($2.slice(hex ? 2 : 1), hex ? 16 : 10);
  }
  return decodeNamedCharacterReference($2) || $0;
}

// node_modules/.pnpm/unist-util-stringify-position@4.0.0/node_modules/unist-util-stringify-position/lib/index.js
function stringifyPosition(value) {
  if (!value || typeof value !== "object") {
    return "";
  }
  if ("position" in value || "type" in value) {
    return position(value.position);
  }
  if ("start" in value || "end" in value) {
    return position(value);
  }
  if ("line" in value || "column" in value) {
    return point(value);
  }
  return "";
}
function point(point3) {
  return index(point3 && point3.line) + ":" + index(point3 && point3.column);
}
function position(pos) {
  return point(pos && pos.start) + "-" + point(pos && pos.end);
}
function index(value) {
  return value && typeof value === "number" ? value : 1;
}

// node_modules/.pnpm/mdast-util-from-markdown@2.1.0/node_modules/mdast-util-from-markdown/lib/index.js
var own2 = {}.hasOwnProperty;
function fromMarkdown(value, encoding, options) {
  if (encoding && typeof encoding === "object") {
    options = encoding;
    encoding = void 0;
  }
  return compiler(options)(postprocess(parse(options).document().write(preprocess()(value, encoding, true))));
}
function compiler(options) {
  const config = {
    afterExit: [],
    beforeEnter: [],
    transforms: [],
    canContainEols: ["emphasis", "fragment", "heading", "paragraph", "strong"],
    enter: {
      autolink: opener(link2),
      autolinkProtocol: onenterdata,
      autolinkEmail: onenterdata,
      atxHeading: opener(heading2),
      blockQuote: opener(blockQuote2),
      characterEscape: onenterdata,
      characterReference: onenterdata,
      codeFenced: opener(codeFlow),
      codeFencedFenceInfo: buffer,
      codeFencedFenceMeta: buffer,
      codeIndented: opener(codeFlow, buffer),
      codeText: opener(codeText2, buffer),
      codeTextData: onenterdata,
      data: onenterdata,
      codeFlowValue: onenterdata,
      definition: opener(definition3),
      definitionDestinationString: buffer,
      definitionLabelString: buffer,
      definitionTitleString: buffer,
      emphasis: opener(emphasis2),
      hardBreakEscape: opener(hardBreak2),
      hardBreakTrailing: opener(hardBreak2),
      htmlFlow: opener(html2, buffer),
      htmlFlowData: onenterdata,
      htmlText: opener(html2, buffer),
      htmlTextData: onenterdata,
      image: opener(image2),
      label: buffer,
      link: opener(link2),
      listItem: opener(listItem2),
      listItemValue: onenterlistitemvalue,
      listOrdered: opener(list4, onenterlistordered),
      listUnordered: opener(list4),
      paragraph: opener(paragraph2),
      reference: onenterreference,
      referenceString: buffer,
      resourceDestinationString: buffer,
      resourceTitleString: buffer,
      setextHeading: opener(heading2),
      strong: opener(strong2),
      thematicBreak: opener(thematicBreak3)
    },
    exit: {
      atxHeading: closer(),
      atxHeadingSequence: onexitatxheadingsequence,
      autolink: closer(),
      autolinkEmail: onexitautolinkemail,
      autolinkProtocol: onexitautolinkprotocol,
      blockQuote: closer(),
      characterEscapeValue: onexitdata,
      characterReferenceMarkerHexadecimal: onexitcharacterreferencemarker,
      characterReferenceMarkerNumeric: onexitcharacterreferencemarker,
      characterReferenceValue: onexitcharacterreferencevalue,
      characterReference: onexitcharacterreference,
      codeFenced: closer(onexitcodefenced),
      codeFencedFence: onexitcodefencedfence,
      codeFencedFenceInfo: onexitcodefencedfenceinfo,
      codeFencedFenceMeta: onexitcodefencedfencemeta,
      codeFlowValue: onexitdata,
      codeIndented: closer(onexitcodeindented),
      codeText: closer(onexitcodetext),
      codeTextData: onexitdata,
      data: onexitdata,
      definition: closer(),
      definitionDestinationString: onexitdefinitiondestinationstring,
      definitionLabelString: onexitdefinitionlabelstring,
      definitionTitleString: onexitdefinitiontitlestring,
      emphasis: closer(),
      hardBreakEscape: closer(onexithardbreak),
      hardBreakTrailing: closer(onexithardbreak),
      htmlFlow: closer(onexithtmlflow),
      htmlFlowData: onexitdata,
      htmlText: closer(onexithtmltext),
      htmlTextData: onexitdata,
      image: closer(onexitimage),
      label: onexitlabel,
      labelText: onexitlabeltext,
      lineEnding: onexitlineending,
      link: closer(onexitlink),
      listItem: closer(),
      listOrdered: closer(),
      listUnordered: closer(),
      paragraph: closer(),
      referenceString: onexitreferencestring,
      resourceDestinationString: onexitresourcedestinationstring,
      resourceTitleString: onexitresourcetitlestring,
      resource: onexitresource,
      setextHeading: closer(onexitsetextheading),
      setextHeadingLineSequence: onexitsetextheadinglinesequence,
      setextHeadingText: onexitsetextheadingtext,
      strong: closer(),
      thematicBreak: closer()
    }
  };
  configure(config, (options || {}).mdastExtensions || []);
  const data = {};
  return compile;
  function compile(events) {
    let tree = {
      type: "root",
      children: [],
      position: void 0
    };
    const context = {
      stack: [tree],
      tokenStack: [],
      config,
      enter,
      exit: exit2,
      buffer,
      resume,
      data
    };
    const listStack = [];
    const prepared = [];
    let index2 = -1;
    while (++index2 < events.length) {
      prepared.push(events[index2]);
      if (events[index2][1].type === "listOrdered" || events[index2][1].type === "listUnordered") {
        if (events[index2][0] === "enter") {
          listStack.push(prepared.length - 1);
        } else {
          const tail = listStack.pop();
          prepareList(prepared, tail);
        }
      }
    }
    events = prepared;
    index2 = -1;
    while (++index2 < events.length) {
      const handler = config[events[index2][0]];
      if (events[index2][0] === "enter" && config.beforeEnter.length > 0) {
        callListeners(config.beforeEnter, {
          ...context,
          sliceSerialize: events[index2][2].sliceSerialize
        }, events[index2][1]);
      }
      if (own2.call(handler, events[index2][1].type)) {
        handler[events[index2][1].type].call({
          ...context,
          sliceSerialize: events[index2][2].sliceSerialize
        }, events[index2][1]);
      }
      if (events[index2][0] === "exit" && config.afterExit.length > 0) {
        callListeners(config.afterExit, {
          ...context,
          sliceSerialize: events[index2][2].sliceSerialize
        }, events[index2][1]);
      }
    }
    if (context.tokenStack.length > 0) {
      const tail = context.tokenStack[context.tokenStack.length - 1];
      const handler = tail[1] || defaultOnError;
      handler.call(context, void 0, tail[0]);
    }
    tree.position = {
      start: point2(events.length > 0 ? events[0][1].start : {
        line: 1,
        column: 1,
        offset: 0
      }),
      end: point2(events.length > 0 ? events[events.length - 2][1].end : {
        line: 1,
        column: 1,
        offset: 0
      })
    };
    index2 = -1;
    while (++index2 < config.transforms.length) {
      tree = config.transforms[index2](tree) || tree;
    }
    return tree;
  }
  function callListeners(listeners, context, token) {
    let index2 = -1;
    while (++index2 < listeners.length) {
      listeners[index2].call(context, token);
    }
  }
  function prepareList(events, start) {
    const end = events.length - 1;
    let index2 = start - 1;
    let containerBalance = -1;
    let listSpread = false;
    let listItem3;
    let lineIndex;
    let firstBlankLineIndex;
    let atMarker;
    const insertions = [];
    while (++index2 <= end) {
      const event = events[index2];
      switch (event[1].type) {
        case "listUnordered":
        case "listOrdered":
        case "blockQuote": {
          if (event[0] === "enter") {
            containerBalance++;
          } else {
            containerBalance--;
          }
          atMarker = void 0;
          break;
        }
        case "lineEndingBlank": {
          if (event[0] === "enter") {
            if (listItem3 && !atMarker && !containerBalance && !firstBlankLineIndex) {
              firstBlankLineIndex = index2;
            }
            atMarker = void 0;
          }
          break;
        }
        case "linePrefix":
        case "listItemValue":
        case "listItemMarker":
        case "listItemPrefix":
        case "listItemPrefixWhitespace": {
          break;
        }
        default: {
          atMarker = void 0;
        }
      }
      if (!containerBalance && event[0] === "enter" && event[1].type === "listItemPrefix" || containerBalance === -1 && event[0] === "exit" && (event[1].type === "listUnordered" || event[1].type === "listOrdered")) {
        if (listItem3) {
          let tailIndex = index2;
          lineIndex = void 0;
          while (tailIndex--) {
            const tailEvent = events[tailIndex];
            if (tailEvent[1].type === "lineEnding" || tailEvent[1].type === "lineEndingBlank") {
              if (tailEvent[0] === "exit") continue;
              if (lineIndex) {
                events[lineIndex][1].type = "lineEndingBlank";
                listSpread = true;
              }
              tailEvent[1].type = "lineEnding";
              lineIndex = tailIndex;
            } else if (tailEvent[1].type === "linePrefix" || tailEvent[1].type === "blockQuotePrefix" || tailEvent[1].type === "blockQuotePrefixWhitespace" || tailEvent[1].type === "blockQuoteMarker" || tailEvent[1].type === "listItemIndent") {
            } else {
              break;
            }
          }
          if (firstBlankLineIndex && (!lineIndex || firstBlankLineIndex < lineIndex)) {
            listItem3._spread = true;
          }
          listItem3.end = Object.assign({}, lineIndex ? events[lineIndex][1].start : event[1].end);
          insertions.push({
            at: lineIndex || index2,
            event: ["exit", listItem3, event[2]]
          });
        }
        if (event[1].type === "listItemPrefix") {
          const item = {
            type: "listItem",
            _spread: false,
            start: Object.assign({}, event[1].start),
            // @ts-expect-error: we’ll add `end` in a second.
            end: void 0
          };
          listItem3 = item;
          insertions.push({
            at: index2,
            event: ["enter", item, event[2]]
          });
          firstBlankLineIndex = void 0;
          atMarker = true;
        }
      }
    }
    const listEvents = events.splice(start);
    let insertion = 0;
    index2 = -1;
    while (++index2 < listEvents.length) {
      while (insertion < insertions.length && insertions[insertion].at === start + index2) {
        events.push(insertions[insertion++].event);
      }
      events.push(listEvents[index2]);
    }
    events[start][1]._spread = listSpread;
  }
  function opener(create, and) {
    return open;
    function open(token) {
      enter.call(this, create(token), token);
      if (and) and.call(this, token);
    }
  }
  function buffer() {
    this.stack.push({
      type: "fragment",
      children: []
    });
  }
  function enter(node2, token, errorHandler) {
    const parent = this.stack[this.stack.length - 1];
    const siblings = parent.children;
    siblings.push(node2);
    this.stack.push(node2);
    this.tokenStack.push([token, errorHandler || void 0]);
    node2.position = {
      start: point2(token.start),
      // @ts-expect-error: `end` will be patched later.
      end: void 0
    };
  }
  function closer(and) {
    return close2;
    function close2(token) {
      if (and) and.call(this, token);
      exit2.call(this, token);
    }
  }
  function exit2(token, onExitError) {
    const node2 = this.stack.pop();
    const open = this.tokenStack.pop();
    if (!open) {
      throw new Error("Cannot close `" + token.type + "` (" + stringifyPosition({
        start: token.start,
        end: token.end
      }) + "): it’s not open");
    }
    if (open[0].type !== token.type) {
      if (onExitError) {
        onExitError.call(this, token, open[0]);
      } else {
        const handler = open[1] || defaultOnError;
        handler.call(this, token, open[0]);
      }
    }
    node2.position.end = point2(token.end);
  }
  function resume() {
    return toString(this.stack.pop());
  }
  function onenterlistordered() {
    this.data.expectingFirstListItemValue = true;
  }
  function onenterlistitemvalue(token) {
    if (this.data.expectingFirstListItemValue) {
      const ancestor = this.stack[this.stack.length - 2];
      ancestor.start = Number.parseInt(this.sliceSerialize(token), 10);
      this.data.expectingFirstListItemValue = void 0;
    }
  }
  function onexitcodefencedfenceinfo() {
    const data2 = this.resume();
    const node2 = this.stack[this.stack.length - 1];
    node2.lang = data2;
  }
  function onexitcodefencedfencemeta() {
    const data2 = this.resume();
    const node2 = this.stack[this.stack.length - 1];
    node2.meta = data2;
  }
  function onexitcodefencedfence() {
    if (this.data.flowCodeInside) return;
    this.buffer();
    this.data.flowCodeInside = true;
  }
  function onexitcodefenced() {
    const data2 = this.resume();
    const node2 = this.stack[this.stack.length - 1];
    node2.value = data2.replace(/^(\r?\n|\r)|(\r?\n|\r)$/g, "");
    this.data.flowCodeInside = void 0;
  }
  function onexitcodeindented() {
    const data2 = this.resume();
    const node2 = this.stack[this.stack.length - 1];
    node2.value = data2.replace(/(\r?\n|\r)$/g, "");
  }
  function onexitdefinitionlabelstring(token) {
    const label = this.resume();
    const node2 = this.stack[this.stack.length - 1];
    node2.label = label;
    node2.identifier = normalizeIdentifier(this.sliceSerialize(token)).toLowerCase();
  }
  function onexitdefinitiontitlestring() {
    const data2 = this.resume();
    const node2 = this.stack[this.stack.length - 1];
    node2.title = data2;
  }
  function onexitdefinitiondestinationstring() {
    const data2 = this.resume();
    const node2 = this.stack[this.stack.length - 1];
    node2.url = data2;
  }
  function onexitatxheadingsequence(token) {
    const node2 = this.stack[this.stack.length - 1];
    if (!node2.depth) {
      const depth = this.sliceSerialize(token).length;
      node2.depth = depth;
    }
  }
  function onexitsetextheadingtext() {
    this.data.setextHeadingSlurpLineEnding = true;
  }
  function onexitsetextheadinglinesequence(token) {
    const node2 = this.stack[this.stack.length - 1];
    node2.depth = this.sliceSerialize(token).codePointAt(0) === 61 ? 1 : 2;
  }
  function onexitsetextheading() {
    this.data.setextHeadingSlurpLineEnding = void 0;
  }
  function onenterdata(token) {
    const node2 = this.stack[this.stack.length - 1];
    const siblings = node2.children;
    let tail = siblings[siblings.length - 1];
    if (!tail || tail.type !== "text") {
      tail = text4();
      tail.position = {
        start: point2(token.start),
        // @ts-expect-error: we’ll add `end` later.
        end: void 0
      };
      siblings.push(tail);
    }
    this.stack.push(tail);
  }
  function onexitdata(token) {
    const tail = this.stack.pop();
    tail.value += this.sliceSerialize(token);
    tail.position.end = point2(token.end);
  }
  function onexitlineending(token) {
    const context = this.stack[this.stack.length - 1];
    if (this.data.atHardBreak) {
      const tail = context.children[context.children.length - 1];
      tail.position.end = point2(token.end);
      this.data.atHardBreak = void 0;
      return;
    }
    if (!this.data.setextHeadingSlurpLineEnding && config.canContainEols.includes(context.type)) {
      onenterdata.call(this, token);
      onexitdata.call(this, token);
    }
  }
  function onexithardbreak() {
    this.data.atHardBreak = true;
  }
  function onexithtmlflow() {
    const data2 = this.resume();
    const node2 = this.stack[this.stack.length - 1];
    node2.value = data2;
  }
  function onexithtmltext() {
    const data2 = this.resume();
    const node2 = this.stack[this.stack.length - 1];
    node2.value = data2;
  }
  function onexitcodetext() {
    const data2 = this.resume();
    const node2 = this.stack[this.stack.length - 1];
    node2.value = data2;
  }
  function onexitlink() {
    const node2 = this.stack[this.stack.length - 1];
    if (this.data.inReference) {
      const referenceType = this.data.referenceType || "shortcut";
      node2.type += "Reference";
      node2.referenceType = referenceType;
      delete node2.url;
      delete node2.title;
    } else {
      delete node2.identifier;
      delete node2.label;
    }
    this.data.referenceType = void 0;
  }
  function onexitimage() {
    const node2 = this.stack[this.stack.length - 1];
    if (this.data.inReference) {
      const referenceType = this.data.referenceType || "shortcut";
      node2.type += "Reference";
      node2.referenceType = referenceType;
      delete node2.url;
      delete node2.title;
    } else {
      delete node2.identifier;
      delete node2.label;
    }
    this.data.referenceType = void 0;
  }
  function onexitlabeltext(token) {
    const string3 = this.sliceSerialize(token);
    const ancestor = this.stack[this.stack.length - 2];
    ancestor.label = decodeString(string3);
    ancestor.identifier = normalizeIdentifier(string3).toLowerCase();
  }
  function onexitlabel() {
    const fragment = this.stack[this.stack.length - 1];
    const value = this.resume();
    const node2 = this.stack[this.stack.length - 1];
    this.data.inReference = true;
    if (node2.type === "link") {
      const children = fragment.children;
      node2.children = children;
    } else {
      node2.alt = value;
    }
  }
  function onexitresourcedestinationstring() {
    const data2 = this.resume();
    const node2 = this.stack[this.stack.length - 1];
    node2.url = data2;
  }
  function onexitresourcetitlestring() {
    const data2 = this.resume();
    const node2 = this.stack[this.stack.length - 1];
    node2.title = data2;
  }
  function onexitresource() {
    this.data.inReference = void 0;
  }
  function onenterreference() {
    this.data.referenceType = "collapsed";
  }
  function onexitreferencestring(token) {
    const label = this.resume();
    const node2 = this.stack[this.stack.length - 1];
    node2.label = label;
    node2.identifier = normalizeIdentifier(this.sliceSerialize(token)).toLowerCase();
    this.data.referenceType = "full";
  }
  function onexitcharacterreferencemarker(token) {
    this.data.characterReferenceType = token.type;
  }
  function onexitcharacterreferencevalue(token) {
    const data2 = this.sliceSerialize(token);
    const type = this.data.characterReferenceType;
    let value;
    if (type) {
      value = decodeNumericCharacterReference(data2, type === "characterReferenceMarkerNumeric" ? 10 : 16);
      this.data.characterReferenceType = void 0;
    } else {
      const result = decodeNamedCharacterReference(data2);
      value = result;
    }
    const tail = this.stack[this.stack.length - 1];
    tail.value += value;
  }
  function onexitcharacterreference(token) {
    const tail = this.stack.pop();
    tail.position.end = point2(token.end);
  }
  function onexitautolinkprotocol(token) {
    onexitdata.call(this, token);
    const node2 = this.stack[this.stack.length - 1];
    node2.url = this.sliceSerialize(token);
  }
  function onexitautolinkemail(token) {
    onexitdata.call(this, token);
    const node2 = this.stack[this.stack.length - 1];
    node2.url = "mailto:" + this.sliceSerialize(token);
  }
  function blockQuote2() {
    return {
      type: "blockquote",
      children: [],
      position: void 0
    };
  }
  function codeFlow() {
    return {
      type: "code",
      lang: null,
      meta: null,
      value: "",
      position: void 0
    };
  }
  function codeText2() {
    return {
      type: "inlineCode",
      value: "",
      position: void 0
    };
  }
  function definition3() {
    return {
      type: "definition",
      identifier: "",
      label: null,
      title: null,
      url: "",
      position: void 0
    };
  }
  function emphasis2() {
    return {
      type: "emphasis",
      children: [],
      position: void 0
    };
  }
  function heading2() {
    return {
      type: "heading",
      // @ts-expect-error `depth` will be set later.
      depth: 0,
      children: [],
      position: void 0
    };
  }
  function hardBreak2() {
    return {
      type: "break",
      position: void 0
    };
  }
  function html2() {
    return {
      type: "html",
      value: "",
      position: void 0
    };
  }
  function image2() {
    return {
      type: "image",
      title: null,
      url: "",
      alt: null,
      position: void 0
    };
  }
  function link2() {
    return {
      type: "link",
      title: null,
      url: "",
      children: [],
      position: void 0
    };
  }
  function list4(token) {
    return {
      type: "list",
      ordered: token.type === "listOrdered",
      start: null,
      spread: token._spread,
      children: [],
      position: void 0
    };
  }
  function listItem2(token) {
    return {
      type: "listItem",
      spread: token._spread,
      checked: null,
      children: [],
      position: void 0
    };
  }
  function paragraph2() {
    return {
      type: "paragraph",
      children: [],
      position: void 0
    };
  }
  function strong2() {
    return {
      type: "strong",
      children: [],
      position: void 0
    };
  }
  function text4() {
    return {
      type: "text",
      value: "",
      position: void 0
    };
  }
  function thematicBreak3() {
    return {
      type: "thematicBreak",
      position: void 0
    };
  }
}
function point2(d) {
  return {
    line: d.line,
    column: d.column,
    offset: d.offset
  };
}
function configure(combined, extensions) {
  let index2 = -1;
  while (++index2 < extensions.length) {
    const value = extensions[index2];
    if (Array.isArray(value)) {
      configure(combined, value);
    } else {
      extension(combined, value);
    }
  }
}
function extension(combined, extension2) {
  let key2;
  for (key2 in extension2) {
    if (own2.call(extension2, key2)) {
      switch (key2) {
        case "canContainEols": {
          const right = extension2[key2];
          if (right) {
            combined[key2].push(...right);
          }
          break;
        }
        case "transforms": {
          const right = extension2[key2];
          if (right) {
            combined[key2].push(...right);
          }
          break;
        }
        case "afterExit":
        case "beforeEnter": {
          const right = extension2[key2];
          if (right) {
            combined[key2].push(right);
          }
          break;
        }
        case "enter":
        case "exit": {
          const right = extension2[key2];
          if (right) {
            Object.assign(combined[key2], right);
          }
          break;
        }
      }
    }
  }
}
function defaultOnError(left, right) {
  if (left) {
    throw new Error("Cannot close `" + left.type + "` (" + stringifyPosition({
      start: left.start,
      end: left.end
    }) + "): a different token (`" + right.type + "`, " + stringifyPosition({
      start: right.start,
      end: right.end
    }) + ") is open");
  }
  throw new Error("Cannot close document, a token (`" + right.type + "`, " + stringifyPosition({
    start: right.start,
    end: right.end
  }) + ") is still open");
}

// node_modules/.pnpm/unist-util-is@6.0.1/node_modules/unist-util-is/lib/index.js
var convert = (
  // Note: overloads in JSDoc can’t yet use different `@template`s.
  /**
   * @type {(
   *   (<Condition extends string>(test: Condition) => (node: unknown, index?: number | null | undefined, parent?: Parent | null | undefined, context?: unknown) => node is Node & {type: Condition}) &
   *   (<Condition extends Props>(test: Condition) => (node: unknown, index?: number | null | undefined, parent?: Parent | null | undefined, context?: unknown) => node is Node & Condition) &
   *   (<Condition extends TestFunction>(test: Condition) => (node: unknown, index?: number | null | undefined, parent?: Parent | null | undefined, context?: unknown) => node is Node & Predicate<Condition, Node>) &
   *   ((test?: null | undefined) => (node?: unknown, index?: number | null | undefined, parent?: Parent | null | undefined, context?: unknown) => node is Node) &
   *   ((test?: Test) => Check)
   * )}
   */
  /**
   * @param {Test} [test]
   * @returns {Check}
   */
  (function(test) {
    if (test === null || test === void 0) {
      return ok;
    }
    if (typeof test === "function") {
      return castFactory(test);
    }
    if (typeof test === "object") {
      return Array.isArray(test) ? anyFactory(test) : (
        // Cast because `ReadonlyArray` goes into the above but `isArray`
        // narrows to `Array`.
        propertiesFactory(
          /** @type {Props} */
          test
        )
      );
    }
    if (typeof test === "string") {
      return typeFactory(test);
    }
    throw new Error("Expected function, string, or object as test");
  })
);
function anyFactory(tests) {
  const checks = [];
  let index2 = -1;
  while (++index2 < tests.length) {
    checks[index2] = convert(tests[index2]);
  }
  return castFactory(any);
  function any(...parameters) {
    let index3 = -1;
    while (++index3 < checks.length) {
      if (checks[index3].apply(this, parameters)) return true;
    }
    return false;
  }
}
function propertiesFactory(check2) {
  const checkAsRecord = (
    /** @type {Record<string, unknown>} */
    check2
  );
  return castFactory(all2);
  function all2(node2) {
    const nodeAsRecord = (
      /** @type {Record<string, unknown>} */
      /** @type {unknown} */
      node2
    );
    let key2;
    for (key2 in check2) {
      if (nodeAsRecord[key2] !== checkAsRecord[key2]) return false;
    }
    return true;
  }
}
function typeFactory(check2) {
  return castFactory(type);
  function type(node2) {
    return node2 && node2.type === check2;
  }
}
function castFactory(testFunction) {
  return check2;
  function check2(value, index2, parent) {
    return Boolean(
      looksLikeANode(value) && testFunction.call(
        this,
        value,
        typeof index2 === "number" ? index2 : void 0,
        parent || void 0
      )
    );
  }
}
function ok() {
  return true;
}
function looksLikeANode(value) {
  return value !== null && typeof value === "object" && "type" in value;
}

// node_modules/.pnpm/mdast-util-phrasing@4.1.0/node_modules/mdast-util-phrasing/lib/index.js
var phrasing = (
  /** @type {(node?: unknown) => node is Exclude<PhrasingContent, Html>} */
  convert([
    "break",
    "delete",
    "emphasis",
    // To do: next major: removed since footnotes were added to GFM.
    "footnote",
    "footnoteReference",
    "image",
    "imageReference",
    "inlineCode",
    // Enabled by `mdast-util-math`:
    "inlineMath",
    "link",
    "linkReference",
    // Enabled by `mdast-util-mdx`:
    "mdxJsxTextElement",
    // Enabled by `mdast-util-mdx`:
    "mdxTextExpression",
    "strong",
    "text",
    // Enabled by `mdast-util-directive`:
    "textDirective"
  ])
);

// node_modules/.pnpm/zwitch@2.0.4/node_modules/zwitch/index.js
var own3 = {}.hasOwnProperty;
function zwitch(key2, options) {
  const settings = options || {};
  function one2(value, ...parameters) {
    let fn = one2.invalid;
    const handlers2 = one2.handlers;
    if (value && own3.call(value, key2)) {
      const id = String(value[key2]);
      fn = own3.call(handlers2, id) ? handlers2[id] : one2.unknown;
    }
    if (fn) {
      return fn.call(this, value, ...parameters);
    }
  }
  one2.handlers = settings.handlers || {};
  one2.invalid = settings.invalid;
  one2.unknown = settings.unknown;
  return one2;
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/configure.js
var own4 = {}.hasOwnProperty;
function configure2(base2, extension2) {
  let index2 = -1;
  let key2;
  if (extension2.extensions) {
    while (++index2 < extension2.extensions.length) {
      configure2(base2, extension2.extensions[index2]);
    }
  }
  for (key2 in extension2) {
    if (own4.call(extension2, key2)) {
      switch (key2) {
        case "extensions": {
          break;
        }
        /* c8 ignore next 4 */
        case "unsafe": {
          list2(base2[key2], extension2[key2]);
          break;
        }
        case "join": {
          list2(base2[key2], extension2[key2]);
          break;
        }
        case "handlers": {
          map2(base2[key2], extension2[key2]);
          break;
        }
        default: {
          base2.options[key2] = extension2[key2];
        }
      }
    }
  }
  return base2;
}
function list2(left, right) {
  if (right) {
    left.push(...right);
  }
}
function map2(left, right) {
  if (right) {
    Object.assign(left, right);
  }
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/handle/blockquote.js
function blockquote(node2, _, state, info) {
  const exit2 = state.enter("blockquote");
  const tracker = state.createTracker(info);
  tracker.move("> ");
  tracker.shift(2);
  const value = state.indentLines(
    state.containerFlow(node2, tracker.current()),
    map3
  );
  exit2();
  return value;
}
function map3(line, _, blank) {
  return ">" + (blank ? "" : " ") + line;
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/util/pattern-in-scope.js
function patternInScope(stack, pattern) {
  return listInScope(stack, pattern.inConstruct, true) && !listInScope(stack, pattern.notInConstruct, false);
}
function listInScope(stack, list4, none2) {
  if (typeof list4 === "string") {
    list4 = [list4];
  }
  if (!list4 || list4.length === 0) {
    return none2;
  }
  let index2 = -1;
  while (++index2 < list4.length) {
    if (stack.includes(list4[index2])) {
      return true;
    }
  }
  return false;
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/handle/break.js
function hardBreak(_, _1, state, info) {
  let index2 = -1;
  while (++index2 < state.unsafe.length) {
    const pattern = state.unsafe[index2];
    if (pattern.character === "\n" && !pattern.before && !pattern.after && patternInScope(state.stack, pattern)) {
      return /[\t ]/.test(info.before) ? "" : " ";
    }
  }
  return "\\\n";
}

// node_modules/.pnpm/longest-streak@3.1.0/node_modules/longest-streak/index.js
function longestStreak(value, substring) {
  const source = String(value);
  let index2 = source.indexOf(substring);
  let expected = index2;
  let count = 0;
  let max = 0;
  if (typeof substring !== "string") {
    throw new TypeError("Expected substring");
  }
  while (index2 !== -1) {
    if (index2 === expected) {
      if (++count > max) {
        max = count;
      }
    } else {
      count = 1;
    }
    expected = index2 + substring.length;
    index2 = source.indexOf(substring, expected);
  }
  return max;
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/util/format-code-as-indented.js
function formatCodeAsIndented(node2, state) {
  return Boolean(
    state.options.fences === false && node2.value && // If there’s no info…
    !node2.lang && // And there’s a non-whitespace character…
    /[^\n\r ]/.test(node2.value) && // And the value doesn’t start or end in a blank…
    !/^[\t ]*(?:[\n\r]|$)|(?:^|[\n\r])[\t ]*$/.test(node2.value)
  );
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/util/check-fence.js
function checkFence(state) {
  const marker = state.options.fence || "`";
  if (marker !== "`" && marker !== "~") {
    throw new Error(
      "Cannot serialize code with `" + marker + "` for `options.fence`, expected `` ` `` or `~`"
    );
  }
  return marker;
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/handle/code.js
function code2(node2, _, state, info) {
  const marker = checkFence(state);
  const raw = node2.value || "";
  if (formatCodeAsIndented(node2, state)) {
    const exit3 = state.enter("codeIndented");
    const value2 = state.indentLines(raw, map4);
    exit3();
    return value2;
  }
  const tracker = state.createTracker(info);
  const sequence = marker.repeat(Math.max(longestStreak(raw, marker) + 1, 3));
  const exit2 = state.enter("codeFenced");
  const suffix = marker === "`" ? "GraveAccent" : "Tilde";
  let value = tracker.move(sequence);
  if (node2.lang) {
    const subexit = state.enter(`codeFencedLang${suffix}`);
    value += tracker.move(
      state.safe(node2.lang, {
        before: value,
        after: " ",
        encode: ["`"],
        ...tracker.current()
      })
    );
    subexit();
  }
  if (node2.lang && node2.meta) {
    const subexit = state.enter(`codeFencedMeta${suffix}`);
    value += tracker.move(" ");
    value += tracker.move(
      state.safe(node2.meta, {
        before: value,
        after: "\n",
        encode: ["`"],
        ...tracker.current()
      })
    );
    subexit();
  }
  value += tracker.move("\n");
  if (raw) {
    value += tracker.move(raw + "\n");
  }
  value += tracker.move(sequence);
  exit2();
  return value;
}
function map4(line, _, blank) {
  return (blank ? "" : "    ") + line;
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/util/check-quote.js
function checkQuote(state) {
  const marker = state.options.quote || '"';
  if (marker !== '"' && marker !== "'") {
    throw new Error(
      "Cannot serialize title with `" + marker + "` for `options.quote`, expected `\"`, or `'`"
    );
  }
  return marker;
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/handle/definition.js
function definition2(node2, _, state, info) {
  const quote = checkQuote(state);
  const suffix = quote === '"' ? "Quote" : "Apostrophe";
  const exit2 = state.enter("definition");
  let subexit = state.enter("label");
  const tracker = state.createTracker(info);
  let value = tracker.move("[");
  value += tracker.move(
    state.safe(state.associationId(node2), {
      before: value,
      after: "]",
      ...tracker.current()
    })
  );
  value += tracker.move("]: ");
  subexit();
  if (
    // If there’s no url, or…
    !node2.url || // If there are control characters or whitespace.
    /[\0- \u007F]/.test(node2.url)
  ) {
    subexit = state.enter("destinationLiteral");
    value += tracker.move("<");
    value += tracker.move(
      state.safe(node2.url, { before: value, after: ">", ...tracker.current() })
    );
    value += tracker.move(">");
  } else {
    subexit = state.enter("destinationRaw");
    value += tracker.move(
      state.safe(node2.url, {
        before: value,
        after: node2.title ? " " : "\n",
        ...tracker.current()
      })
    );
  }
  subexit();
  if (node2.title) {
    subexit = state.enter(`title${suffix}`);
    value += tracker.move(" " + quote);
    value += tracker.move(
      state.safe(node2.title, {
        before: value,
        after: quote,
        ...tracker.current()
      })
    );
    value += tracker.move(quote);
    subexit();
  }
  exit2();
  return value;
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/util/check-emphasis.js
function checkEmphasis(state) {
  const marker = state.options.emphasis || "*";
  if (marker !== "*" && marker !== "_") {
    throw new Error(
      "Cannot serialize emphasis with `" + marker + "` for `options.emphasis`, expected `*`, or `_`"
    );
  }
  return marker;
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/handle/emphasis.js
emphasis.attention = attention2;
emphasis.peek = peek;
function emphasis(node2, _, state, info) {
  const exit2 = state.enter("phrasing");
  const value = state.containerPhrasing({ type: "root", children: [node2] }, info);
  exit2();
  return value;
}
function attention2(_, state) {
  const marker = checkEmphasis(state);
  return {
    construct: "emphasis",
    markers: marker === "*" ? ["*", "_"] : ["_", "*"],
    sizes: [1]
  };
}
function peek(_, _1, state) {
  return state.options.emphasis || "*";
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/util/encode-character-reference.js
function encodeCharacterReference(code4) {
  return "&#x" + code4.toString(16).toUpperCase() + ";";
}

// node_modules/.pnpm/unist-util-visit-parents@6.0.2/node_modules/unist-util-visit-parents/lib/color.js
function color(d) {
  return d;
}

// node_modules/.pnpm/unist-util-visit-parents@6.0.2/node_modules/unist-util-visit-parents/lib/index.js
var empty2 = [];
var CONTINUE = true;
var EXIT = false;
var SKIP = "skip";
function visitParents(tree, test, visitor, reverse) {
  let check2;
  if (typeof test === "function" && typeof visitor !== "function") {
    reverse = visitor;
    visitor = test;
  } else {
    check2 = test;
  }
  const is2 = convert(check2);
  const step = reverse ? -1 : 1;
  factory(tree, void 0, [])();
  function factory(node2, index2, parents) {
    const value = (
      /** @type {Record<string, unknown>} */
      node2 && typeof node2 === "object" ? node2 : {}
    );
    if (typeof value.type === "string") {
      const name = (
        // `hast`
        typeof value.tagName === "string" ? value.tagName : (
          // `xast`
          typeof value.name === "string" ? value.name : void 0
        )
      );
      Object.defineProperty(visit2, "name", {
        value: "node (" + color(node2.type + (name ? "<" + name + ">" : "")) + ")"
      });
    }
    return visit2;
    function visit2() {
      let result = empty2;
      let subresult;
      let offset;
      let grandparents;
      if (!test || is2(node2, index2, parents[parents.length - 1] || void 0)) {
        result = toResult(visitor(node2, parents));
        if (result[0] === EXIT) {
          return result;
        }
      }
      if ("children" in node2 && node2.children) {
        const nodeAsParent = (
          /** @type {UnistParent} */
          node2
        );
        if (nodeAsParent.children && result[0] !== SKIP) {
          offset = (reverse ? nodeAsParent.children.length : -1) + step;
          grandparents = parents.concat(nodeAsParent);
          while (offset > -1 && offset < nodeAsParent.children.length) {
            const child = nodeAsParent.children[offset];
            subresult = factory(child, offset, grandparents)();
            if (subresult[0] === EXIT) {
              return subresult;
            }
            offset = typeof subresult[1] === "number" ? subresult[1] : offset + step;
          }
        }
      }
      return result;
    }
  }
}
function toResult(value) {
  if (Array.isArray(value)) {
    return value;
  }
  if (typeof value === "number") {
    return [CONTINUE, value];
  }
  return value === null || value === void 0 ? empty2 : [value];
}

// node_modules/.pnpm/unist-util-visit@5.1.0/node_modules/unist-util-visit/lib/index.js
function visit(tree, testOrVisitor, visitorOrReverse, maybeReverse) {
  let reverse;
  let test;
  let visitor;
  if (typeof testOrVisitor === "function" && typeof visitorOrReverse !== "function") {
    test = void 0;
    visitor = testOrVisitor;
    reverse = visitorOrReverse;
  } else {
    test = testOrVisitor;
    visitor = visitorOrReverse;
    reverse = maybeReverse;
  }
  visitParents(tree, test, overload, reverse);
  function overload(node2, parents) {
    const parent = parents[parents.length - 1];
    const index2 = parent ? parent.children.indexOf(node2) : void 0;
    return visitor(node2, index2, parent);
  }
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/util/format-heading-as-setext.js
function formatHeadingAsSetext(node2, state) {
  let literalWithBreak = false;
  visit(node2, function(node3) {
    if ("value" in node3 && /\r?\n|\r/.test(node3.value) || node3.type === "break") {
      literalWithBreak = true;
      return EXIT;
    }
  });
  return Boolean(
    (!node2.depth || node2.depth < 3) && toString(node2) && (state.options.setext || literalWithBreak)
  );
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/handle/heading.js
function heading(node2, _, state, info) {
  const rank = Math.max(Math.min(6, node2.depth || 1), 1);
  const tracker = state.createTracker(info);
  if (formatHeadingAsSetext(node2, state)) {
    const exit3 = state.enter("headingSetext");
    const subexit2 = state.enter("phrasing");
    const value2 = state.containerPhrasing(node2, {
      ...tracker.current(),
      before: "\n",
      after: "\n"
    });
    subexit2();
    exit3();
    return value2 + "\n" + (rank === 1 ? "=" : "-").repeat(
      // The whole size…
      value2.length - // Minus the position of the character after the last EOL (or
      // 0 if there is none)…
      (Math.max(value2.lastIndexOf("\r"), value2.lastIndexOf("\n")) + 1)
    );
  }
  const sequence = "#".repeat(rank);
  const exit2 = state.enter("headingAtx");
  const subexit = state.enter("phrasing");
  tracker.move(sequence + " ");
  let value = state.containerPhrasing(node2, {
    before: "# ",
    after: "\n",
    ...tracker.current()
  });
  const head = value.charCodeAt(0);
  if (head === 9 || head === 32) {
    value = encodeCharacterReference(head) + value.slice(1);
  }
  value = value ? sequence + " " + value : sequence;
  if (state.options.closeAtx) {
    value += " " + sequence;
  }
  subexit();
  exit2();
  return value;
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/handle/html.js
html.peek = htmlPeek;
function html(node2) {
  return node2.value || "";
}
function htmlPeek() {
  return "<";
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/handle/image.js
image.peek = imagePeek;
function image(node2, _, state, info) {
  const quote = checkQuote(state);
  const suffix = quote === '"' ? "Quote" : "Apostrophe";
  const exit2 = state.enter("image");
  let subexit = state.enter("label");
  const tracker = state.createTracker(info);
  let value = tracker.move("![");
  value += tracker.move(
    state.safe(node2.alt, { before: value, after: "]", ...tracker.current() })
  );
  value += tracker.move("](");
  subexit();
  if (
    // If there’s no url but there is a title…
    !node2.url && node2.title || // If there are control characters or whitespace.
    /[\0- \u007F]/.test(node2.url)
  ) {
    subexit = state.enter("destinationLiteral");
    value += tracker.move("<");
    value += tracker.move(
      state.safe(node2.url, { before: value, after: ">", ...tracker.current() })
    );
    value += tracker.move(">");
  } else {
    subexit = state.enter("destinationRaw");
    value += tracker.move(
      state.safe(node2.url, {
        before: value,
        after: node2.title ? " " : ")",
        ...tracker.current()
      })
    );
  }
  subexit();
  if (node2.title) {
    subexit = state.enter(`title${suffix}`);
    value += tracker.move(" " + quote);
    value += tracker.move(
      state.safe(node2.title, {
        before: value,
        after: quote,
        ...tracker.current()
      })
    );
    value += tracker.move(quote);
    subexit();
  }
  value += tracker.move(")");
  exit2();
  return value;
}
function imagePeek() {
  return "!";
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/handle/image-reference.js
imageReference.peek = imageReferencePeek;
function imageReference(node2, _, state, info) {
  const type = node2.referenceType;
  const exit2 = state.enter("imageReference");
  let subexit = state.enter("label");
  const tracker = state.createTracker(info);
  let value = tracker.move("![");
  const alt = state.safe(node2.alt, {
    before: value,
    after: "]",
    ...tracker.current()
  });
  value += tracker.move(alt + "][");
  subexit();
  const stack = state.stack;
  state.stack = stack.filter(function(d) {
    return d !== "phrasing";
  });
  subexit = state.enter("reference");
  const reference = state.safe(state.associationId(node2), {
    before: value,
    after: "]",
    ...tracker.current()
  });
  subexit();
  state.stack = stack;
  exit2();
  if (type === "full" || !alt || alt !== reference) {
    value += tracker.move(reference + "]");
  } else if (type === "shortcut") {
    value = value.slice(0, -1);
  } else {
    value += tracker.move("]");
  }
  return value;
}
function imageReferencePeek() {
  return "!";
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/handle/inline-code.js
inlineCode.peek = inlineCodePeek;
function inlineCode(node2, _, state) {
  let value = node2.value || "";
  let sequence = "`";
  let index2 = -1;
  while (new RegExp("(^|[^`])" + sequence + "([^`]|$)").test(value)) {
    sequence += "`";
  }
  if (/[^\n\r ]/.test(value) && (/^[\n\r ]/.test(value) && /[\n\r ]$/.test(value) || /^`|`$/.test(value))) {
    value = " " + value + " ";
  }
  while (++index2 < state.unsafe.length) {
    const pattern = state.unsafe[index2];
    const expression = state.compilePattern(pattern);
    if (!pattern.atBreak) continue;
    let match;
    while (match = expression.exec(value)) {
      let position2 = match.index;
      if (value.charCodeAt(position2) === 10 && value.charCodeAt(position2 - 1) === 13) {
        position2--;
      }
      value = value.slice(0, position2) + " " + value.slice(match.index + 1);
    }
  }
  return sequence + value + sequence;
}
function inlineCodePeek() {
  return "`";
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/util/format-link-as-autolink.js
function formatLinkAsAutolink(node2, state) {
  const raw = toString(node2);
  return Boolean(
    !state.options.resourceLink && // If there’s a url…
    node2.url && // And there’s no title…
    !node2.title && // And the content of `node` is a single text node…
    node2.children && node2.children.length === 1 && node2.children[0].type === "text" && // And if the url is the same as the content…
    (raw === node2.url || "mailto:" + raw === node2.url) && // And that starts w/ a protocol…
    /^[a-z][+\-.a-z]+:/i.test(node2.url) && // And that doesn’t contain ASCII control codes (character escapes and
    // references don’t work), space, or angle brackets…
    !/[\0- <>\u007F]/.test(node2.url)
  );
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/handle/link.js
link.peek = linkPeek;
function link(node2, _, state, info) {
  const quote = checkQuote(state);
  const suffix = quote === '"' ? "Quote" : "Apostrophe";
  const tracker = state.createTracker(info);
  if (formatLinkAsAutolink(node2, state)) {
    const stack = state.stack;
    state.stack = stack.filter(function(d) {
      return d !== "phrasing";
    });
    const exit3 = state.enter("autolink");
    let value2 = tracker.move("<");
    value2 += tracker.move(
      state.containerPhrasing(node2, {
        before: value2,
        after: ">",
        ...tracker.current()
      })
    );
    value2 += tracker.move(">");
    exit3();
    state.stack = stack;
    return value2;
  }
  const exit2 = state.enter("link");
  let subexit = state.enter("label");
  let value = tracker.move("[");
  value += tracker.move(
    state.containerPhrasing(node2, {
      before: value,
      after: "](",
      ...tracker.current()
    })
  );
  value += tracker.move("](");
  subexit();
  if (
    // If there’s no url but there is a title…
    !node2.url && node2.title || // If there are control characters or whitespace.
    /[\0- \u007F]/.test(node2.url)
  ) {
    subexit = state.enter("destinationLiteral");
    value += tracker.move("<");
    value += tracker.move(
      state.safe(node2.url, { before: value, after: ">", ...tracker.current() })
    );
    value += tracker.move(">");
  } else {
    subexit = state.enter("destinationRaw");
    value += tracker.move(
      state.safe(node2.url, {
        before: value,
        after: node2.title ? " " : ")",
        ...tracker.current()
      })
    );
  }
  subexit();
  if (node2.title) {
    subexit = state.enter(`title${suffix}`);
    value += tracker.move(" " + quote);
    value += tracker.move(
      state.safe(node2.title, {
        before: value,
        after: quote,
        ...tracker.current()
      })
    );
    value += tracker.move(quote);
    subexit();
  }
  value += tracker.move(")");
  exit2();
  return value;
}
function linkPeek(node2, _, state) {
  return formatLinkAsAutolink(node2, state) ? "<" : "[";
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/handle/link-reference.js
linkReference.peek = linkReferencePeek;
function linkReference(node2, _, state, info) {
  const type = node2.referenceType;
  const exit2 = state.enter("linkReference");
  let subexit = state.enter("label");
  const tracker = state.createTracker(info);
  let value = tracker.move("[");
  const text4 = state.containerPhrasing(node2, {
    before: value,
    after: "]",
    ...tracker.current()
  });
  value += tracker.move(text4 + "][");
  subexit();
  const stack = state.stack;
  state.stack = stack.filter(function(d) {
    return d !== "phrasing";
  });
  subexit = state.enter("reference");
  const reference = state.safe(state.associationId(node2), {
    before: value,
    after: "]",
    ...tracker.current()
  });
  subexit();
  state.stack = stack;
  exit2();
  if (type === "full" || !text4 || text4 !== reference) {
    value += tracker.move(reference + "]");
  } else if (type === "shortcut") {
    value = value.slice(0, -1);
  } else {
    value += tracker.move("]");
  }
  return value;
}
function linkReferencePeek() {
  return "[";
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/util/check-bullet.js
function checkBullet(state) {
  const marker = state.options.bullet || "*";
  if (marker !== "*" && marker !== "+" && marker !== "-") {
    throw new Error(
      "Cannot serialize items with `" + marker + "` for `options.bullet`, expected `*`, `+`, or `-`"
    );
  }
  return marker;
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/util/check-bullet-other.js
function checkBulletOther(state) {
  const bullet = checkBullet(state);
  const bulletOther = state.options.bulletOther;
  if (!bulletOther) {
    return bullet === "*" ? "-" : "*";
  }
  if (bulletOther !== "*" && bulletOther !== "+" && bulletOther !== "-") {
    throw new Error(
      "Cannot serialize items with `" + bulletOther + "` for `options.bulletOther`, expected `*`, `+`, or `-`"
    );
  }
  if (bulletOther === bullet) {
    throw new Error(
      "Expected `bullet` (`" + bullet + "`) and `bulletOther` (`" + bulletOther + "`) to be different"
    );
  }
  return bulletOther;
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/util/check-bullet-ordered.js
function checkBulletOrdered(state) {
  const marker = state.options.bulletOrdered || ".";
  if (marker !== "." && marker !== ")") {
    throw new Error(
      "Cannot serialize items with `" + marker + "` for `options.bulletOrdered`, expected `.` or `)`"
    );
  }
  return marker;
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/util/check-rule.js
function checkRule(state) {
  const marker = state.options.rule || "*";
  if (marker !== "*" && marker !== "-" && marker !== "_") {
    throw new Error(
      "Cannot serialize rules with `" + marker + "` for `options.rule`, expected `*`, `-`, or `_`"
    );
  }
  return marker;
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/handle/list.js
function list3(node2, parent, state, info) {
  const exit2 = state.enter("list");
  const bulletCurrent = state.bulletCurrent;
  let bullet = node2.ordered ? checkBulletOrdered(state) : checkBullet(state);
  const bulletOther = node2.ordered ? bullet === "." ? ")" : "." : checkBulletOther(state);
  let useDifferentMarker = parent && state.bulletLastUsed ? bullet === state.bulletLastUsed : false;
  if (!node2.ordered) {
    const firstListItem = node2.children ? node2.children[0] : void 0;
    if (
      // Bullet could be used as a thematic break marker:
      (bullet === "*" || bullet === "-") && // Empty first list item:
      firstListItem && (!firstListItem.children || !firstListItem.children[0]) && // Directly in two other list items:
      state.stack[state.stack.length - 1] === "list" && state.stack[state.stack.length - 2] === "listItem" && state.stack[state.stack.length - 3] === "list" && state.stack[state.stack.length - 4] === "listItem" && // That are each the first child.
      state.indexStack[state.indexStack.length - 1] === 0 && state.indexStack[state.indexStack.length - 2] === 0 && state.indexStack[state.indexStack.length - 3] === 0
    ) {
      useDifferentMarker = true;
    }
    if (checkRule(state) === bullet && firstListItem) {
      let index2 = -1;
      while (++index2 < node2.children.length) {
        const item = node2.children[index2];
        if (item && item.type === "listItem" && item.children && item.children[0] && item.children[0].type === "thematicBreak") {
          useDifferentMarker = true;
          break;
        }
      }
    }
  }
  if (useDifferentMarker) {
    bullet = bulletOther;
  }
  state.bulletCurrent = bullet;
  const value = state.containerFlow(node2, info);
  state.bulletLastUsed = bullet;
  state.bulletCurrent = bulletCurrent;
  exit2();
  return value;
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/util/check-list-item-indent.js
function checkListItemIndent(state) {
  const style = state.options.listItemIndent || "one";
  if (style !== "tab" && style !== "one" && style !== "mixed") {
    throw new Error(
      "Cannot serialize items with `" + style + "` for `options.listItemIndent`, expected `tab`, `one`, or `mixed`"
    );
  }
  return style;
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/handle/list-item.js
function listItem(node2, parent, state, info) {
  const listItemIndent = checkListItemIndent(state);
  let bullet = state.bulletCurrent || checkBullet(state);
  if (parent && parent.type === "list" && parent.ordered) {
    bullet = (typeof parent.start === "number" && parent.start > -1 ? parent.start : 1) + (state.options.incrementListMarker === false ? 0 : parent.children.indexOf(node2)) + bullet;
  }
  let size = bullet.length + 1;
  if (listItemIndent === "tab" || listItemIndent === "mixed" && (parent && parent.type === "list" && parent.spread || node2.spread)) {
    size = Math.ceil(size / 4) * 4;
  }
  const tracker = state.createTracker(info);
  tracker.move(bullet + " ".repeat(size - bullet.length));
  tracker.shift(size);
  const exit2 = state.enter("listItem");
  const value = state.indentLines(
    state.containerFlow(node2, tracker.current()),
    map5
  );
  exit2();
  return value;
  function map5(line, index2, blank) {
    if (index2) {
      return (blank ? "" : " ".repeat(size)) + line;
    }
    return (blank ? bullet : bullet + " ".repeat(size - bullet.length)) + line;
  }
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/handle/paragraph.js
function paragraph(node2, _, state, info) {
  const exit2 = state.enter("paragraph");
  const subexit = state.enter("phrasing");
  const value = state.containerPhrasing(node2, info);
  subexit();
  exit2();
  return value;
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/handle/root.js
function root(node2, _, state, info) {
  const hasPhrasing = node2.children.some(function(d) {
    return phrasing(d);
  });
  if (!hasPhrasing) return state.containerFlow(node2, info);
  const exit2 = state.enter("phrasing");
  const value = state.containerPhrasing(node2, info);
  exit2();
  return value;
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/util/check-strong.js
function checkStrong(state) {
  const marker = state.options.strong || "*";
  if (marker !== "*" && marker !== "_") {
    throw new Error(
      "Cannot serialize strong with `" + marker + "` for `options.strong`, expected `*`, or `_`"
    );
  }
  return marker;
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/handle/strong.js
strong.attention = attention3;
strong.peek = peek2;
function strong(node2, _, state, info) {
  const exit2 = state.enter("phrasing");
  const value = state.containerPhrasing({ type: "root", children: [node2] }, info);
  exit2();
  return value;
}
function attention3(_, state) {
  const marker = checkStrong(state);
  return {
    construct: "strong",
    markers: marker === "*" ? ["*", "_"] : ["_", "*"],
    sizes: [2]
  };
}
function peek2(_, _1, state) {
  return state.options.strong || "*";
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/handle/text.js
function text3(node2, parent, state, info) {
  const siblings = parent ? parent.children : [];
  const index2 = siblings.indexOf(node2);
  return state.safe(node2.value, {
    ...info,
    afterNode: siblings[index2 + 1],
    beforeNode: siblings[index2 - 1]
  });
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/util/check-rule-repetition.js
function checkRuleRepetition(state) {
  const repetition = state.options.ruleRepetition || 3;
  if (repetition < 3) {
    throw new Error(
      "Cannot serialize rules with repetition `" + repetition + "` for `options.ruleRepetition`, expected `3` or more"
    );
  }
  return repetition;
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/handle/thematic-break.js
function thematicBreak2(_, _1, state) {
  const value = (checkRule(state) + (state.options.ruleSpaces ? " " : "")).repeat(checkRuleRepetition(state));
  return state.options.ruleSpaces ? value.slice(0, -1) : value;
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/handle/index.js
var handle = {
  blockquote,
  break: hardBreak,
  code: code2,
  definition: definition2,
  emphasis,
  hardBreak,
  heading,
  html,
  image,
  imageReference,
  inlineCode,
  link,
  linkReference,
  list: list3,
  listItem,
  paragraph,
  root,
  strong,
  text: text3,
  thematicBreak: thematicBreak2
};

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/util/html-kind.js
function htmlKind(value) {
  if (value.charCodeAt(0) !== 60) return;
  const next = value.charCodeAt(1);
  if (next === 33) {
    const code5 = value.charCodeAt(2);
    if (code5 === 45) return 2;
    if (code5 === 91) return 5;
    if (asciiAlpha(code5)) return 4;
    return;
  }
  if (next === 63) return 3;
  const closing = next === 47;
  const start = closing ? 2 : 1;
  let end = start;
  let code4 = value.charCodeAt(end);
  if (!asciiAlpha(code4)) return;
  while (code4 === 45 || asciiAlphanumeric(code4)) {
    code4 = value.charCodeAt(++end);
  }
  const name = value.slice(start, end).toLowerCase();
  if (!closing && code4 !== 47 && htmlRawNames.includes(name)) {
    return 1;
  }
  return htmlBlockNames.includes(name) ? 6 : 7;
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/join.js
var join2 = [joinDefaults];
function joinDefaults(left, right, parent, state) {
  if (right.type === "code" && formatCodeAsIndented(right, state) && (left.type === "list" || left.type === right.type && formatCodeAsIndented(left, state))) {
    return false;
  }
  if ("spread" in parent && typeof parent.spread === "boolean") {
    if (left.type === "paragraph" && // Two paragraphs.
    (left.type === right.type || right.type === "definition" || // Paragraph followed by a setext heading.
    right.type === "heading" && formatHeadingAsSetext(right, state))) {
      return;
    }
    if (left.type === "html") {
      const kind = htmlKind(left.value);
      if (kind === void 0 || kind === 6 || kind === 7) return 1;
    }
    if (left.type === "paragraph" && right.type === "html") {
      const kind = htmlKind(right.value);
      if (kind === void 0 || kind === 7) return 1;
    }
    return parent.spread ? 1 : 0;
  }
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/unsafe.js
var fullPhrasingSpans = [
  "autolink",
  "destinationLiteral",
  "destinationRaw",
  "reference",
  "titleQuote",
  "titleApostrophe"
];
var unsafe = [
  { character: "	", after: "[\\r\\n]", inConstruct: "phrasing" },
  { character: "	", before: "[\\r\\n]", inConstruct: "phrasing" },
  {
    character: "	",
    inConstruct: ["codeFencedLangGraveAccent", "codeFencedLangTilde"]
  },
  {
    character: "\r",
    inConstruct: [
      "codeFencedLangGraveAccent",
      "codeFencedLangTilde",
      "codeFencedMetaGraveAccent",
      "codeFencedMetaTilde",
      "destinationLiteral",
      "headingAtx"
    ]
  },
  {
    character: "\n",
    inConstruct: [
      "codeFencedLangGraveAccent",
      "codeFencedLangTilde",
      "codeFencedMetaGraveAccent",
      "codeFencedMetaTilde",
      "destinationLiteral",
      "headingAtx"
    ]
  },
  { character: "\r", before: "[\\r\\n]", inConstruct: "phrasing" },
  { character: "\r", after: "\\r", inConstruct: "phrasing" },
  { character: "\n", before: "\\n", inConstruct: "phrasing" },
  { character: "\n", after: "[\\r\\n]", inConstruct: "phrasing" },
  { character: " ", after: "[\\r\\n]", inConstruct: "phrasing" },
  { character: " ", before: "[\\r\\n]", inConstruct: "phrasing" },
  {
    character: " ",
    inConstruct: ["codeFencedLangGraveAccent", "codeFencedLangTilde"]
  },
  // An exclamation mark can start an image, if it is followed by a link or
  // a link reference.
  {
    character: "!",
    after: "\\[",
    inConstruct: "phrasing",
    notInConstruct: fullPhrasingSpans
  },
  // A quote can break out of a title.
  { character: '"', inConstruct: "titleQuote" },
  // A number sign could start an ATX heading if it starts a line.
  { atBreak: true, character: "#" },
  { character: "#", inConstruct: "headingAtx", after: "(?:[\r\n]|$)" },
  // Dollar sign and percentage are not used in markdown.
  // An ampersand could start a character reference.
  { character: "&", after: "[#A-Za-z]", inConstruct: "phrasing" },
  // An apostrophe can break out of a title.
  { character: "'", inConstruct: "titleApostrophe" },
  // A left paren could break out of a destination raw.
  { character: "(", inConstruct: "destinationRaw" },
  // A left paren followed by `]` could make something into a link or image.
  {
    before: "\\]",
    character: "(",
    inConstruct: "phrasing",
    notInConstruct: fullPhrasingSpans
  },
  // A right paren could start a list item or break out of a destination
  // raw.
  { atBreak: true, before: "\\d+", character: ")" },
  { character: ")", inConstruct: "destinationRaw" },
  // An asterisk can start thematic breaks, list items, emphasis, strong.
  { atBreak: true, character: "*", after: "(?:[ 	\r\n*])" },
  { character: "*", inConstruct: "phrasing", notInConstruct: fullPhrasingSpans },
  // A plus sign could start a list item.
  { atBreak: true, character: "+", after: "(?:[ 	\r\n])" },
  // A dash can start thematic breaks, list items, and setext heading
  // underlines.
  { atBreak: true, character: "-", after: "(?:[ 	\r\n-])" },
  // A dot could start a list item.
  { atBreak: true, before: "\\d+", character: ".", after: "(?:[ 	\r\n]|$)" },
  // Slash, colon, and semicolon are not used in markdown for constructs.
  // A less than can start html (flow or text) or an autolink.
  // HTML could start with an exclamation mark (declaration, cdata, comment),
  // slash (closing tag), question mark (instruction), or a letter (tag).
  // An autolink also starts with a letter.
  // Finally, it could break out of a destination literal.
  { atBreak: true, character: "<", after: "[!/?A-Za-z]" },
  {
    character: "<",
    after: "[!/?A-Za-z]",
    inConstruct: "phrasing",
    notInConstruct: fullPhrasingSpans
  },
  { character: "<", inConstruct: "destinationLiteral" },
  // An equals to can start setext heading underlines.
  { atBreak: true, character: "=" },
  // A greater than can start block quotes and it can break out of a
  // destination literal.
  { atBreak: true, character: ">" },
  { character: ">", inConstruct: "destinationLiteral" },
  // Question mark and at sign are not used in markdown for constructs.
  // A left bracket can start definitions, references, labels,
  { atBreak: true, character: "[" },
  { character: "[", inConstruct: "phrasing", notInConstruct: fullPhrasingSpans },
  { character: "[", inConstruct: ["label", "reference"] },
  // A backslash can start an escape (when followed by punctuation) or a
  // hard break (when followed by an eol).
  // Note: typical escapes are handled in `safe`!
  { character: "\\", after: "[\\r\\n]", inConstruct: "phrasing" },
  // A right bracket can exit labels.
  { character: "]", inConstruct: ["label", "reference"] },
  // Caret is not used in markdown for constructs.
  // An underscore can start emphasis, strong, or a thematic break.
  { atBreak: true, character: "_" },
  { character: "_", inConstruct: "phrasing", notInConstruct: fullPhrasingSpans },
  // A grave accent can start code (fenced or text), or it can break out of
  // a grave accent code fence.
  { atBreak: true, character: "`" },
  {
    character: "`",
    inConstruct: ["codeFencedLangGraveAccent", "codeFencedMetaGraveAccent"]
  },
  { character: "`", inConstruct: "phrasing", notInConstruct: fullPhrasingSpans },
  // Left brace, vertical bar, right brace are not used in markdown for
  // constructs.
  // A tilde can start code (fenced).
  { atBreak: true, character: "~" },
  { character: "<", inConstruct: "autolink" },
  { character: ">", inConstruct: "autolink" },
  { character: "", inConstruct: "autolink" }
];
var code3 = -1;
while (++code3 < 33) {
  unsafe.push({ character: String.fromCharCode(code3), inConstruct: "autolink" });
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/util/association.js
function association(node2) {
  if (node2.label || !node2.identifier) {
    return node2.label || "";
  }
  return decodeString(node2.identifier);
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/util/compile-pattern.js
function compilePattern(pattern) {
  if (!pattern._compiled) {
    const before = (pattern.atBreak ? "[\\r\\n][\\t ]*" : "") + (pattern.before ? "(?:" + pattern.before + ")" : "");
    pattern._compiled = new RegExp(
      (pattern.beforeNode ? "^" : before ? "(" + before + ")" : "") + (/[$()*+.?[\\\]^{|}]/.test(pattern.character) ? "\\" : "") + pattern.character + (pattern.afterNode ? "$" : pattern.after ? "(?:" + pattern.after + ")" : ""),
      pattern.unicode ? "gu" : "g"
    );
  }
  return pattern._compiled;
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/util/character.js
function firstCharacter(value) {
  const code4 = value.codePointAt(0);
  return code4 === void 0 ? "" : String.fromCodePoint(code4);
}
function lastCharacter(value) {
  const code4 = value.codePointAt(value.length - 2);
  return code4 !== void 0 && code4 > 65535 ? value.slice(-2) : value.slice(-1);
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/util/encode-info.js
function encodeInfo(outside, inside, marker) {
  const outsideKind = classifyCharacter(outside);
  const insideKind = classifyCharacter(inside);
  if (outsideKind === void 0) {
    return insideKind === void 0 ? (
      // Letter inside:
      // we have to encode *both* letters for `_` as it is looser.
      // it already forms for `*` (and GFMs `~`).
      marker === "_" ? { inside: true, outside: true } : { inside: false, outside: false }
    ) : insideKind === 1 ? (
      // Whitespace inside: encode both (letter, whitespace).
      { inside: true, outside: true }
    ) : (
      // Punctuation inside: encode outer (letter)
      { inside: false, outside: true }
    );
  }
  if (outsideKind === 1) {
    return insideKind === void 0 ? (
      // Letter inside: already forms.
      { inside: false, outside: false }
    ) : insideKind === 1 ? (
      // Whitespace inside: encode both (whitespace).
      { inside: true, outside: true }
    ) : (
      // Punctuation inside: already forms.
      { inside: false, outside: false }
    );
  }
  return insideKind === void 0 ? (
    // Letter inside: already forms.
    { inside: false, outside: false }
  ) : insideKind === 1 ? (
    // Whitespace inside: encode inner (whitespace).
    { inside: true, outside: false }
  ) : (
    // Punctuation inside: already forms.
    { inside: false, outside: false }
  );
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/util/container-phrasing.js
var builtins = /* @__PURE__ */ new Map([
  ["*", false],
  ["_", true]
]);
function candidates(tokens, involved, runOf) {
  const related = /* @__PURE__ */ new Set();
  for (const token of tokens) {
    const siblings = runOf.get(token);
    if (siblings && token.attention && involved.some((d) => d.attention === token.attention)) {
      for (const sibling of siblings.tokens) {
        related.add(sibling.attention);
      }
    }
  }
  const ordered = [];
  for (const token of tokens) {
    if (token.attention && related.delete(token.attention)) {
      ordered.push(token.attention);
    }
  }
  ordered.reverse();
  return ordered;
}
function check(tokens, before, after) {
  const runs = [];
  const wrong = /* @__PURE__ */ new Map();
  const runOf = /* @__PURE__ */ new Map();
  let index2 = 0;
  while (index2 < tokens.length) {
    if (!tokens[index2].attention) {
      index2++;
      continue;
    }
    const marker = tokens[index2].value.charAt(0);
    const strict = builtins.get(marker);
    let end = index2 + 1;
    while (end < tokens.length && tokens[end].attention && tokens[end].value.charAt(0) === marker) {
      end++;
    }
    const head = index2 ? tokens[index2 - 1].value : before;
    const previous2 = classifyCharacter(head.charCodeAt(head.length - 1));
    const next = classifyCharacter(
      (end < tokens.length ? tokens[end].value : after).charCodeAt(0)
    );
    const open = !next || next === 2 && Boolean(previous2);
    const close2 = !previous2 || previous2 === 2 && Boolean(next);
    const run = {
      tokens: tokens.slice(index2, end),
      markers: [],
      start: 0,
      end: 0,
      // Underscores are strict, they cannot open or close inside words.
      open: strict ? open && (Boolean(previous2) || !close2) : open,
      close: strict ? close2 && (Boolean(next) || !open) : close2,
      // All builtins can split runs.
      split: strict !== void 0
    };
    for (const token of run.tokens) {
      wrong.set(token, [...run.tokens]);
      runOf.set(token, run);
      let size = token.value.length;
      while (size--) run.markers.push(token);
    }
    run.end = run.markers.length;
    runs.push(run);
    index2 = end;
  }
  pair(runs, wrong);
  index2 = -1;
  while (++index2 < tokens.length) {
    const involved = wrong.get(tokens[index2]);
    if (involved) return { attention: candidates(tokens, involved, runOf), index: index2 };
  }
}
function containerPhrasing(parent, state, info) {
  return serialize(phrasing2(parent, state, info), info.before, info.after);
}
function encode(tokens, start) {
  const token = tokens[start ? 0 : tokens.length - 1];
  if (!token || token.attention) return;
  const character = start ? firstCharacter(token.value) : lastCharacter(token.value);
  const reference = encodeCharacterReference(
    /** @type {number} */
    character.codePointAt(0)
  );
  token.value = start ? reference + token.value.slice(character.length) : token.value.slice(0, token.value.length - character.length) + reference;
}
function improve(items, chosen, mistake, before, after) {
  for (const attention4 of mistake.attention) {
    const current = chosen.get(attention4) || attention4.sequences[0];
    for (const sequence of attention4.sequences) {
      if (sequence === current) continue;
      const trial = new Map(chosen);
      trial.set(attention4, sequence);
      const tokens = render(items, trial, before, after);
      const next = check(tokens, before, after);
      if (!next || next.index > mistake.index) {
        return { chosen: trial, mistake: next, tokens };
      }
    }
  }
}
function pair(runs, wrong) {
  let index2 = 0;
  while (index2 < runs.length) {
    const closer = runs[index2];
    const marker = closer.tokens[0].value.charAt(0);
    const closerSize = closer.end - closer.start;
    let open = closer.close && closerSize ? index2 : 0;
    while (open--) {
      const opener = runs[open];
      const openerSize = opener.end - opener.start;
      if (opener.tokens[0].value.charAt(0) === marker && opener.open && openerSize && (closer.split ? (
        // The rule of 3, on the sizes that are left.
        !((opener.close || closer.open) && closerSize % 3) || (openerSize + closerSize) % 3
      ) : (
        // Others pair whole runs of the same size.
        openerSize === opener.markers.length && openerSize === closerSize
      ))) {
        const size = closer.split ? openerSize > 1 && closerSize > 1 ? 2 : 1 : closerSize;
        const opening = opener.markers.slice(opener.end - size, opener.end);
        const closing = closer.markers.slice(closer.start, closer.start + size);
        const openToken = opening[0];
        const closeToken = closing[0];
        if (
          // Whole sequences:
          // the markers of a sequence are next to each other,
          // so if the first and last marker are of one sequence of that size,
          // all markers are exactly that sequence.
          openToken === opening[size - 1] && openToken.value.length === size && closeToken === closing[size - 1] && closeToken.value.length === size && // Of the same attention, so its opening and closing sequence.
          openToken.attention === closeToken.attention
        ) {
          wrong.delete(openToken);
          wrong.delete(closeToken);
        } else {
          const involved = [.../* @__PURE__ */ new Set([...opening, ...closing])];
          for (const token of involved) {
            const list4 = wrong.get(token);
            if (list4) list4.push(...involved);
          }
        }
        opener.end -= size;
        closer.start += size;
        break;
      }
    }
    if (open === -1 || closer.start === closer.end) index2++;
  }
}
function attentionSequences(type, markers, sizes) {
  if (markers.length === 0) {
    throw new Error(
      "Cannot serialize `" + type + "` as attention without markers, expected one or more markers"
    );
  }
  if (sizes.length === 0) {
    throw new Error(
      "Cannot serialize `" + type + "` as attention without sizes, expected one or more sizes"
    );
  }
  for (const size of sizes) {
    if (!Number.isSafeInteger(size) || size < 1) {
      throw new Error(
        "Cannot serialize `" + type + "` as attention with `" + size + "` as size, expected positive integer"
      );
    }
  }
  const sequences = [];
  for (const marker of markers) {
    if (marker.length !== 1) {
      throw new Error(
        "Cannot serialize `" + type + "` as attention with `" + marker + "` as marker, expected a single ascii character"
      );
    }
    if (!asciiPunctuation(marker.charCodeAt(0))) {
      throw new Error(
        "Cannot serialize `" + type + "` as attention with `" + marker + "` as marker, expected ascii punctuation"
      );
    }
    for (const size of sizes) {
      sequences.push(marker.repeat(size));
    }
  }
  return sequences;
}
function phrasing2(parent, state, info) {
  const indexStack = state.indexStack;
  const children = parent.children || [];
  const results = [];
  let index2 = -1;
  let before = info.before;
  indexStack.push(-1);
  let tracker = state.createTracker(info);
  while (++index2 < children.length) {
    const child = children[index2];
    let after;
    indexStack[indexStack.length - 1] = index2;
    if (index2 + 1 < children.length) {
      let handle3 = state.handle.handlers[children[index2 + 1].type];
      if (handle3 && handle3.peek) handle3 = handle3.peek;
      after = handle3 ? firstCharacter(
        handle3(children[index2 + 1], parent, state, {
          before: "",
          after: "",
          ...tracker.current()
        })
      ) : "";
    } else {
      after = info.after;
    }
    const previous2 = results[results.length - 1];
    if (typeof previous2 === "string" && (before === "\r" || before === "\n") && child.type === "html" && htmlKind(child.value) !== 7) {
      results[results.length - 1] = previous2.replace(/(\r?\n|\r)$/, " ");
      before = " ";
      tracker = state.createTracker(info);
      tracker.move(serialize(results, info.before, info.after));
    }
    const handle2 = state.handle.handlers[child.type];
    if (handle2 && handle2.attention) {
      const { construct, markers, sizes } = handle2.attention(child, state);
      const sequences = attentionSequences(child.type, markers, sizes);
      const sequence = sequences[0];
      const exit2 = state.enter(construct);
      tracker.move(sequence);
      const inside = phrasing2(
        /** @type {PhrasingParents} */
        child,
        state,
        {
          ...tracker.current(),
          before: sequence,
          after: sequence
        }
      );
      tracker.move(serialize(inside, sequence, sequence));
      tracker.move(sequence);
      exit2();
      results.push({ children: inside, sequences });
      before = sequence.charAt(sequence.length - 1);
    } else {
      const value = state.handle(child, parent, state, {
        ...tracker.current(),
        after,
        before
      });
      if (!value) continue;
      tracker.move(value);
      results.push(value);
      before = lastCharacter(value);
    }
  }
  indexStack.pop();
  return results;
}
function render(items, chosen, before, after) {
  const tokens = [];
  let encodeAfter;
  let previous2 = lastCharacter(before);
  let index2 = -1;
  while (++index2 < items.length) {
    const item = items[index2];
    if (typeof item === "string") {
      const token = { value: item, attention: void 0 };
      if (encodeAfter && encodeAfter === firstCharacter(item)) {
        encode([token], true);
      }
      encodeAfter = void 0;
      tokens.push(token);
      if (token.value) previous2 = lastCharacter(token.value);
      continue;
    }
    const sequence = chosen.get(item) || item.sequences[0];
    const marker = sequence.charAt(0);
    const next = items[index2 + 1];
    const outsideBefore = previous2;
    const outsideAfter = firstCharacter(
      next === void 0 ? after : typeof next === "string" ? next : chosen.get(next) || next.sequences[0]
    );
    const inside = render(item.children, chosen, sequence, sequence);
    const head = inside.length > 0 ? inside[0].value : "";
    const open = encodeInfo(
      outsideBefore.charCodeAt(outsideBefore.length - 1),
      head.charCodeAt(0),
      marker
    );
    if (open.inside) encode(inside, true);
    const tail = inside.length > 0 ? lastCharacter(inside[inside.length - 1].value) : "";
    const close2 = encodeInfo(
      outsideAfter.charCodeAt(0),
      tail.charCodeAt(tail.length - 1),
      marker
    );
    if (close2.inside) encode(inside, false);
    if (open.outside && outsideBefore !== "\n" && outsideBefore !== "\r") {
      encode(tokens, false);
    }
    if (close2.outside) encodeAfter = outsideAfter;
    tokens.push({ value: sequence, attention: item }, ...inside, {
      value: sequence,
      attention: item
    });
    previous2 = sequence.charAt(sequence.length - 1);
  }
  return tokens;
}
function serialize(items, before, after) {
  let chosen = /* @__PURE__ */ new Map();
  const initial = render(items, chosen, before, after);
  let tokens = initial;
  let mistake = check(tokens, before, after);
  while (mistake) {
    const next = improve(items, chosen, mistake, before, after);
    if (!next) {
      tokens = initial;
      break;
    }
    chosen = next.chosen;
    tokens = next.tokens;
    mistake = next.mistake;
  }
  let result = "";
  for (const token of tokens) result += token.value;
  return result;
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/util/container-flow.js
function containerFlow(parent, state, info) {
  const indexStack = state.indexStack;
  const children = parent.children || [];
  const tracker = state.createTracker(info);
  const results = [];
  let index2 = -1;
  indexStack.push(-1);
  while (++index2 < children.length) {
    const child = children[index2];
    indexStack[indexStack.length - 1] = index2;
    results.push(
      tracker.move(
        state.handle(child, parent, state, {
          before: "\n",
          after: "\n",
          ...tracker.current()
        })
      )
    );
    if (child.type !== "list") {
      state.bulletLastUsed = void 0;
    }
    if (index2 < children.length - 1) {
      results.push(
        tracker.move(between(child, children[index2 + 1], parent, state))
      );
    }
  }
  indexStack.pop();
  return results.join("");
}
function between(left, right, parent, state) {
  let index2 = state.join.length;
  while (index2--) {
    const result = state.join[index2](left, right, parent, state);
    if (result === true || result === 1) {
      break;
    }
    if (typeof result === "number") {
      return "\n".repeat(1 + result);
    }
    if (result === false) {
      return "\n\n<!---->\n\n";
    }
  }
  return "\n\n";
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/util/indent-lines.js
var eol = /\r?\n|\r/g;
function indentLines(value, map5) {
  const result = [];
  let start = 0;
  let line = 0;
  let match;
  while (match = eol.exec(value)) {
    one2(value.slice(start, match.index));
    result.push(match[0]);
    start = match.index + match[0].length;
    line++;
  }
  one2(value.slice(start));
  return result.join("");
  function one2(value2) {
    result.push(map5(value2, line, !value2));
  }
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/util/safe.js
var own5 = {}.hasOwnProperty;
function safe(state, input, config) {
  const value = (config.before || "") + (input || "") + (config.after || "");
  const positions = [];
  const result = [];
  const infos = {};
  const percentEncode = state.stack.includes("autolink");
  const offset = config.before ? config.before.length : 0;
  const end = value.length - (config.after ? config.after.length : 0);
  let index2 = -1;
  while (++index2 < state.unsafe.length) {
    const pattern = state.unsafe[index2];
    if (!patternInScope(state.stack, pattern) || !nodeInScope(pattern.beforeNode, config.beforeNode) || !nodeInScope(pattern.afterNode, config.afterNode)) {
      continue;
    }
    const expression = state.compilePattern(pattern);
    const from2 = pattern.beforeNode ? offset : 0;
    const subject = value.slice(from2, pattern.afterNode ? end : void 0);
    let match;
    while (match = expression.exec(subject)) {
      const before = "before" in pattern || Boolean(pattern.atBreak);
      const after = "after" in pattern;
      const position2 = from2 + match.index + (before ? match[1].length : 0);
      if (own5.call(infos, position2)) {
        if (infos[position2].before && !before) {
          infos[position2].before = false;
        }
        if (infos[position2].after && !after) {
          infos[position2].after = false;
        }
      } else {
        positions.push(position2);
        infos[position2] = { before, after };
      }
    }
  }
  positions.sort(numerical);
  let start = offset;
  index2 = -1;
  while (++index2 < positions.length) {
    const position2 = positions[index2];
    if (position2 < start || position2 >= end) {
      continue;
    }
    if (value.charAt(position2) === "_" && // Preceded by an unescaped character that is not punctuation or whitespace:
    position2 > 0 && classifyCharacter(value.charCodeAt(position2 - 1)) === void 0 && !own5.call(infos, position2 - 1) && // Characters next to attention markers can become character references
    // later, turning `a` into `&#x61;`, so those do not count.
    !(position2 - 1 === offset && /[*_]/.test(value.charAt(offset - 1)))) {
      let sequenceEnd = position2 + 1;
      while (sequenceEnd < end && value.charAt(sequenceEnd) === "_") {
        sequenceEnd++;
      }
      const skip = sequenceEnd - position2 - 1;
      if (
        // All underscores in the run are unsafe positions, so they can be
        // skipped.
        positions[index2 + skip] === sequenceEnd - 1 && // Rest as above.
        sequenceEnd < value.length && classifyCharacter(value.charCodeAt(sequenceEnd)) === void 0 && !own5.call(infos, sequenceEnd) && !(sequenceEnd === end - 1 && /[*_]/.test(value.charAt(end)))
      ) {
        index2 += skip;
        continue;
      }
    }
    if (position2 + 1 < end && positions[index2 + 1] === position2 + 1 && infos[position2].after && !infos[position2 + 1].before && !infos[position2 + 1].after || positions[index2 - 1] === position2 - 1 && infos[position2].before && !infos[position2 - 1].before && !infos[position2 - 1].after) {
      continue;
    }
    if (start !== position2) {
      const slice2 = value.slice(start, position2);
      result.push(percentEncode ? slice2 : escapeBackslashes(slice2, "\\"));
    }
    start = position2;
    if (percentEncode) {
      result.push(
        "%" + value.charCodeAt(position2).toString(16).toUpperCase().padStart(2, "0")
      );
      start++;
    } else if (/[!-/:-@[-`{-~]/.test(value.charAt(position2)) && (!config.encode || !config.encode.includes(value.charAt(position2)))) {
      result.push("\\");
    } else {
      result.push(encodeCharacterReference(value.charCodeAt(position2)));
      start++;
    }
  }
  const rest = value.slice(start, end);
  result.push(percentEncode ? rest : escapeBackslashes(rest, config.after));
  return result.join("");
}
function nodeInScope(types, node2) {
  if (!types) return true;
  if (!node2) return false;
  return typeof types === "string" ? types === node2.type : types.includes(node2.type);
}
function numerical(a, b) {
  return a - b;
}
function escapeBackslashes(value, after) {
  const expression = /\\(?=[!-/:-@[-`{-~])/g;
  const positions = [];
  const results = [];
  const whole = value + after;
  let index2 = -1;
  let start = 0;
  let match;
  while (match = expression.exec(whole)) {
    positions.push(match.index);
  }
  while (++index2 < positions.length) {
    if (start !== positions[index2]) {
      results.push(value.slice(start, positions[index2]));
    }
    results.push("\\");
    start = positions[index2];
  }
  results.push(value.slice(start));
  return results.join("");
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/util/track.js
function track(config) {
  const options = config || {};
  const now = options.now || {};
  let lineShift = options.lineShift || 0;
  let line = now.line || 1;
  let column = now.column || 1;
  return { move, current, shift: shift2 };
  function current() {
    return { now: { line, column }, lineShift };
  }
  function shift2(value) {
    lineShift += value;
  }
  function move(input) {
    const value = input || "";
    const chunks = value.split(/\r?\n|\r/g);
    const tail = chunks[chunks.length - 1];
    line += chunks.length - 1;
    column = chunks.length === 1 ? column + tail.length : 1 + tail.length + lineShift;
    return value;
  }
}

// node_modules/.pnpm/mdast-util-to-markdown@2.2.0/node_modules/mdast-util-to-markdown/lib/index.js
function toMarkdown(tree, options) {
  const settings = options || {};
  const state = {
    associationId: association,
    bulletCurrent: void 0,
    bulletLastUsed: void 0,
    containerPhrasing: containerPhrasingBound,
    containerFlow: containerFlowBound,
    createTracker: track,
    compilePattern,
    enter,
    // @ts-expect-error: GFM / frontmatter are typed in `mdast` but not defined
    // here.
    handlers: { ...handle },
    // @ts-expect-error: add `handle` in a second.
    handle: void 0,
    indentLines,
    indexStack: [],
    join: [...join2],
    options: {},
    safe: safeBound,
    stack: [],
    unsafe: [...unsafe]
  };
  configure2(state, settings);
  if (state.options.tightDefinitions) {
    state.join.push(joinDefinition);
  }
  state.handle = zwitch("type", {
    invalid,
    unknown,
    handlers: state.handlers
  });
  let result = state.handle(
    phrasing(tree) ? { type: "root", children: [tree] } : tree,
    void 0,
    state,
    { before: "\n", after: "\n", now: { line: 1, column: 1 }, lineShift: 0 }
  );
  if (result && result.charCodeAt(result.length - 1) !== 10 && result.charCodeAt(result.length - 1) !== 13) {
    result += "\n";
  }
  return result;
  function enter(name) {
    state.stack.push(name);
    return exit2;
    function exit2() {
      state.stack.pop();
    }
  }
}
function invalid(value) {
  throw new Error("Cannot handle value `" + value + "`, expected node");
}
function unknown(value) {
  const node2 = (
    /** @type {Nodes} */
    value
  );
  throw new Error("Cannot handle unknown node `" + node2.type + "`");
}
function joinDefinition(left, right) {
  if (left.type === "definition" && left.type === right.type) {
    return 0;
  }
}
function containerPhrasingBound(parent, info) {
  return containerPhrasing(parent, this, info);
}
function containerFlowBound(parent, info) {
  return containerFlow(parent, this, info);
}
function safeBound(value, config) {
  return safe(this, value, config);
}

// src/source-map.js
function codepointOffset(source, offset) {
  if (!Number.isInteger(offset) || offset < 0 || offset > source.length) throw new RangeError("Invalid UTF-16 offset");
  if (offset && offset < source.length && /[\uD800-\uDBFF]/u.test(source[offset - 1]) && /[\uDC00-\uDFFF]/u.test(source[offset])) {
    throw new RangeError("Offset splits a surrogate pair");
  }
  return [...source.slice(0, offset)].length;
}
function utf16Offset(source, offset) {
  if (!Number.isInteger(offset) || offset < 0) throw new RangeError("Invalid codepoint offset");
  const points = [...source];
  if (offset > points.length) throw new RangeError("Invalid codepoint offset");
  return points.slice(0, offset).join("").length;
}
var SourceMappingError = class extends Error {
};
function toSourceRange({ from: from2, to }, map5) {
  if (!Number.isInteger(from2) || !Number.isInteger(to) || from2 >= to) throw new SourceMappingError("Select nonempty text");
  if (map5.opaque.some((range) => from2 < range.to && to > range.from)) {
    throw new SourceMappingError("Cannot annotate opaque Markdown");
  }
  const start = map5.segments.find((segment) => segment.from === from2);
  const end = map5.segments.findLast((segment) => segment.to === to);
  if (!start || !end || start.sourceFrom >= end.sourceTo) throw new SourceMappingError("Selection has no exact source boundaries");
  return {
    start: codepointOffset(map5.source, start.sourceFrom),
    end: codepointOffset(map5.source, end.sourceTo),
    source_quote: map5.source.slice(start.sourceFrom, end.sourceTo),
    display_quote: map5.doc.textBetween(from2, to, "\n\n", "\n")
  };
}
function toDocumentRange({ start, end }, map5) {
  const left = utf16Offset(map5.source, start), right = utf16Offset(map5.source, end);
  const first = map5.segments.find((unit) => unit.sourceFrom === left);
  const last = map5.segments.findLast((unit) => unit.sourceTo === right);
  if (!first || !last) throw new SourceMappingError("Source has no exact document boundaries");
  const range = { from: first.from, to: last.to };
  const verified = toSourceRange(range, map5);
  if (verified.start !== start || verified.end !== end) throw new SourceMappingError("Source boundaries do not round-trip");
  return range;
}

// src/markdown-bridge.js
var schema = new Schema({
  nodes: {
    doc: { content: "block+" },
    paragraph: { group: "block", content: "inline*", attrs: { sourceId: { default: null } }, toDOM: () => ["p", 0] },
    text: { group: "inline" },
    hard_break: { group: "inline", inline: true, selectable: false, toDOM: () => ["br"] },
    opaque: {
      group: "block",
      atom: true,
      selectable: true,
      attrs: { sourceId: { default: null }, source: { default: "" } },
      leafText: (node2) => node2.attrs.source,
      toDOM: (node2) => ["pre", { "data-opaque": "true", contenteditable: "false" }, node2.attrs.source]
    }
  },
  marks: {
    strong: { toDOM: () => ["strong", 0] },
    em: { toDOM: () => ["em", 0] }
  }
});
var punctuation = /^[!"#$%&'()*+,\-./:;<=>?@[\\\]^_`{|}~]$/;
var supported = (node2) => ["paragraph", "text", "strong", "emphasis", "break"].includes(node2.type) && (!node2.children || node2.children.every(supported));
function lexicalUnits(raw, offset, plain = false) {
  const units = [];
  for (let index2 = 0; index2 < raw.length; ) {
    let length = String.fromCodePoint(raw.codePointAt(index2)).length;
    let value = raw.slice(index2, index2 + length);
    const softBreak = !plain && /^[ \t]*(?:\r\n|[\r\n])[ \t]*/.exec(raw.slice(index2));
    if (softBreak) {
      length = softBreak[0].length;
      value = "\n";
    } else if (!plain && value === "\\" && punctuation.test(raw[index2 + 1] || "")) {
      length = 2;
      value = raw[index2 + 1];
    } else if (!plain && value === "&") {
      const entity = /^(?:&#[0-9]{1,7};|&#x[0-9a-f]{1,6};|&[a-z][a-z0-9]+;)/i.exec(raw.slice(index2));
      if (entity) {
        const parsed = fromMarkdown(entity[0]);
        value = parsed.children[0]?.children[0]?.value ?? entity[0];
        length = entity[0].length;
      }
    } else if (value === "\r") {
      length = raw[index2 + 1] === "\n" ? 2 : 1;
      value = "\n";
    }
    units.push({ value, sourceFrom: offset + index2, sourceTo: offset + index2 + length });
    index2 += length;
  }
  return units;
}
function inlineNodes(ast, source, position2, segments, marks = []) {
  const nodes = [];
  for (const child of ast.children || []) {
    if (child.type === "text") {
      const raw = source.slice(child.position.start.offset, child.position.end.offset);
      const units = lexicalUnits(raw, child.position.start.offset);
      const visible = child.value.replace(/\r\n|\r/g, "\n");
      if (units.map((unit) => unit.value).join("") !== visible) throw new SourceMappingError("Text decoding has no exact source map");
      for (const unit of units) {
        segments.push({ ...unit, from: position2, to: position2 + unit.value.length });
        position2 += unit.value.length;
      }
      if (visible) nodes.push(schema.text(visible, marks));
    } else if (child.type === "break") {
      nodes.push(schema.nodes.hard_break.create());
      segments.push({ from: position2, to: position2 + 1, sourceFrom: child.position.start.offset, sourceTo: child.position.end.offset });
      position2++;
    } else {
      const mark = schema.marks[child.type === "strong" ? "strong" : "em"].create();
      const nested = inlineNodes(child, source, position2, segments, [...marks, mark]);
      nodes.push(...nested.nodes);
      position2 = nested.position;
    }
  }
  return { nodes, position: position2 };
}
function plainBlocks(source) {
  const blocks = [];
  const delimiter = /\r?\n[\t ]*\r?\n|\r(?!\n)[\t ]*\r(?!\n)/g;
  let from2 = 0;
  for (const match of source.matchAll(delimiter)) {
    blocks.push({ start: from2, end: match.index });
    from2 = match.index + match[0].length;
  }
  blocks.push({ start: from2, end: source.length });
  return blocks;
}
function markdownBlocks(source) {
  const ast = fromMarkdown(source).children;
  const blocks = [];
  const empty3 = (offset) => ({ type: "paragraph", children: [], position: { start: { offset }, end: { offset } } });
  if (!ast.length) blocks.push(empty3(0));
  let prior = 0;
  for (let index2 = 0; index2 <= ast.length; index2++) {
    const next = ast[index2];
    const until = next ? next.position.start.offset : source.length;
    const ends = [...source.slice(prior, until).matchAll(/\r\n|[\r\n]/g)];
    const extras = Math.floor(Math.max(0, ends.length - (index2 && next ? 2 : 0)) / 2);
    for (let count = 0; count < extras; count++) {
      const leading = index2 === 0 && next;
      const at = leading ? count * 2 - 1 : (count + 1) * 2 - 1;
      const offset = leading && count === 0 ? 0 : prior + ends[at].index + ends[at][0].length;
      blocks.push(empty3(offset));
    }
    if (next) {
      blocks.push(next);
      prior = next.position.end.offset;
    }
  }
  return blocks;
}
function loadDocument(source, contentFormat = "plain") {
  if (typeof source !== "string" || !["plain", "markdown"].includes(contentFormat)) throw new TypeError("Invalid author text");
  const segments = [], opaque = [], blocks = [], nodes = [];
  const ast = contentFormat === "markdown" ? markdownBlocks(source) : plainBlocks(source);
  let position2 = 0;
  for (const [index2, block] of ast.entries()) {
    const from2 = contentFormat === "markdown" ? block.position.start.offset : block.start;
    const to = contentFormat === "markdown" ? block.position.end.offset : block.end;
    const attrs = { sourceId: `block-${index2}` };
    let node2;
    if (contentFormat === "plain") {
      const raw = source.slice(from2, to);
      const units = lexicalUnits(raw, from2, true);
      const visible = units.map((unit) => unit.value).join("");
      node2 = schema.nodes.paragraph.create(attrs, visible ? schema.text(visible) : null);
      let offset = position2 + 1;
      for (const unit of units) {
        segments.push({ ...unit, from: offset, to: offset + unit.value.length });
        offset += unit.value.length;
      }
    } else if (supported(block)) {
      node2 = schema.nodes.paragraph.create(attrs, inlineNodes(block, source, position2 + 1, segments).nodes);
    } else {
      node2 = schema.nodes.opaque.create({ ...attrs, source: source.slice(from2, to) });
      opaque.push({ from: position2, to: position2 + node2.nodeSize });
    }
    blocks.push({ from: from2, to, node: node2, id: attrs.sourceId });
    nodes.push(node2);
    position2 += node2.nodeSize;
  }
  if (!nodes.length) nodes.push(schema.nodes.paragraph.create({ sourceId: "empty" }));
  const doc3 = schema.nodes.doc.create(null, nodes);
  return { doc: doc3, source, content_format: contentFormat, blocks, sourceMap: { source, doc: doc3, segments, opaque } };
}
function inlineAst(node2) {
  const children = [];
  node2.forEach((child) => {
    if (child.type.name === "hard_break") {
      children.push({ type: "break" });
      return;
    }
    let ast = { type: "text", value: child.text };
    for (const mark of [...child.marks].reverse()) ast = { type: mark.type.name === "strong" ? "strong" : "emphasis", children: [ast] };
    children.push(ast);
  });
  return children;
}
function semantic(node2) {
  if (node2.type.name === "text") return { type: "text", text: node2.text, marks: node2.marks.map((mark) => mark.type.name).sort() };
  if (node2.type.name === "opaque") return { type: "opaque", source: node2.attrs.source };
  const children = [];
  node2.forEach((child) => children.push(semantic(child)));
  return { type: node2.type.name, children };
}
function serializeBlock(node2) {
  if (node2.type.name === "opaque") return node2.attrs.source;
  if (!node2.content.size) return "";
  const source = toMarkdown({ type: "root", children: [{ type: "paragraph", children: inlineAst(node2) }] }, { emphasis: "_", strong: "*" }).replace(/\n$/, "");
  const reparsed = loadDocument(source, "markdown");
  if (JSON.stringify(semantic(reparsed.doc.firstChild)) !== JSON.stringify(semantic(node2))) {
    throw new SourceMappingError("Edited Markdown does not reproduce the document");
  }
  return source;
}
function serializeDocument(doc3, baseline) {
  if (doc3.eq(baseline.doc)) return { source: baseline.source, sourceMap: baseline.sourceMap, content_format: baseline.content_format };
  const nodes = [];
  doc3.forEach((node2) => nodes.push(node2));
  const ids = nodes.map((node2) => node2.attrs.sourceId);
  const previous2 = new Map(baseline.blocks.map((block, index2) => [block.id, { ...block, index: index2 }]));
  const newline = baseline.source.includes("\r\n") ? "\r\n" : "\n";
  let source = "", prior = null;
  for (const node2 of nodes) {
    const old = ids.filter((id) => id === node2.attrs.sourceId).length === 1 ? previous2.get(node2.attrs.sourceId) : null;
    if (prior !== null) source += old && prior && old.index === prior.index + 1 ? baseline.source.slice(prior.to, old.from) : newline + newline;
    else if (old?.index === 0) source += baseline.source.slice(0, old.from);
    const reusable = baseline.content_format === "markdown" && old?.node.eq(node2);
    source += reusable ? baseline.source.slice(old.from, old.to) : serializeBlock(node2).replace(/\r?\n/g, newline);
    prior = old ?? false;
  }
  if (prior && prior.index === baseline.blocks.length - 1) source += baseline.source.slice(prior.to);
  const loaded = loadDocument(source, "markdown");
  if (JSON.stringify(semantic(loaded.doc)) !== JSON.stringify(semantic(doc3))) {
    throw new SourceMappingError("Serialized Markdown does not reproduce the document");
  }
  return { source, sourceMap: loaded.sourceMap, content_format: "markdown" };
}

// src/comment-plugin.js
var key = new PluginKey("obscura-author-comments");
var bindingSequence = 0;
var bind2 = (item) => item.binding ? item : { ...item, binding: "attachment-" + ++bindingSequence };
var geometry = (item) => ({ id: item.id, binding: item.binding, from: item.from, to: item.to, state: item.state, reason: item.reason, origin: item.origin });
var jsonItem = (item) => ({ ...item, origin: item.origin ? { ...item.origin, doc: item.origin.doc?.toJSON() } : null });
var fromJSON = (schema2, item) => ({ ...item, origin: item.origin ? { ...item.origin, doc: item.origin.doc ? schema2.nodeFromJSON(item.origin.doc) : null } : null });
var GeometryStep = class _GeometryStep extends Step {
  constructor(before, after) {
    super();
    this.before = before;
    this.after = after;
  }
  apply(doc3) {
    return StepResult.ok(doc3);
  }
  invert() {
    return new _GeometryStep(this.after, this.before);
  }
  map() {
    return this;
  }
  // Local history only; no collaborative rebasing is enabled.
  toJSON() {
    return { stepType: "obscura-comment-geometry-v1", before: this.before.map(jsonItem), after: this.after.map(jsonItem) };
  }
  static fromJSON(schema2, value) {
    return new _GeometryStep(value.before.map((item) => fromJSON(schema2, item)), value.after.map((item) => fromJSON(schema2, item)));
  }
};
Step.jsonID("obscura-comment-geometry-v1", GeometryStep);
function assertRanges(items, doc3) {
  if (new Set(items.map((item) => item.id)).size !== items.length) throw new Error("Duplicate annotation ID");
  const active = items.filter((item) => item.state === "valid").sort((a, b) => a.from - b.from);
  if (active.some((item) => !Number.isInteger(item.from) || !Number.isInteger(item.to) || item.from < 0 || item.to > doc3.content.size || item.from >= item.to)) throw new Error("Invalid annotation range");
  if (active.some((item, index2) => index2 && item.from < active[index2 - 1].to)) throw new Error("Annotation ranges overlap");
}
function mapItem(item, step) {
  if (!Number.isInteger(item.from) || !Number.isInteger(item.to)) return item;
  const map5 = step.getMap();
  let touched = false;
  map5.forEach((left, right) => {
    if (left === right ? left > item.from && left < item.to : left < item.to && right > item.from) touched = true;
  });
  if (["addMark", "removeMark"].includes(step.toJSON().stepType) && step.from < item.to && step.to > item.from) touched = true;
  const from2 = map5.map(item.from, 1), to = map5.map(item.to, -1);
  return {
    ...item,
    from: Math.min(from2, to),
    to: Math.max(from2, to),
    state: touched ? "needs_review" : item.state,
    reason: touched ? "modified" : item.reason
  };
}
var commentAnnotations = (state) => key.getState(state)?.items || [];
function replaceCommentAnnotations(transaction, items, { silent = false } = {}) {
  return closeHistory(transaction.setMeta(key, { items: items.map(bind2), silent }).setMeta("addToHistory", false));
}
function createCommentPlugin(options = {}) {
  return new Plugin({
    key,
    state: {
      init: (_config, state) => {
        const items = (options.initial || []).map(bind2);
        assertRanges(items, state.doc);
        return { items, silent: true };
      },
      apply(transaction, current) {
        const replacement = transaction.getMeta(key);
        if (replacement) {
          assertRanges(replacement.items, transaction.doc);
          return { items: replacement.items, silent: replacement.silent };
        }
        if (!transaction.docChanged) return current;
        const recorded = transaction.steps.filter((step) => step instanceof GeometryStep);
        let items = current.items.map((item) => {
          const snapshots = recorded.map((step) => step.after.find((value) => value.id === item.id));
          if (recorded.length && snapshots.every((value) => value && value.binding === item.binding)) return { ...item, ...snapshots.at(-1) };
          for (const step of transaction.steps) if (!(step instanceof GeometryStep)) item = mapItem(item, step);
          return item;
        });
        if (isHistoryTransaction(transaction)) items = items.map((item) => {
          if (item.state === "needs_review" && item.origin?.doc?.eq(transaction.doc)) {
            return { ...item, from: item.origin.from, to: item.origin.to, state: "valid", reason: null };
          }
          return item;
        });
        const conflicted = /* @__PURE__ */ new Set();
        for (let i2 = 0; i2 < items.length; i2++) for (let j = i2 + 1; j < items.length; j++) {
          const a = items[i2], b = items[j];
          if (a.state === "valid" && b.state === "valid" && a.from < b.to && b.from < a.to) {
            conflicted.add(a.id);
            conflicted.add(b.id);
          }
        }
        items = items.map((item) => conflicted.has(item.id) ? { ...item, state: "needs_review", reason: "history_overlap" } : item);
        assertRanges(items, transaction.doc);
        return { items, silent: false };
      }
    },
    appendTransaction(transactions, before, after) {
      if (!transactions.some((tr) => tr.docChanged) || transactions.some((tr) => tr.getMeta(key) || tr.getMeta("comments-recorded") || isHistoryTransaction(tr))) return null;
      const old = commentAnnotations(before), updated = commentAnnotations(after);
      if (!old.some((item, index2) => item.from !== updated[index2]?.from || item.to !== updated[index2]?.to || item.state !== updated[index2]?.state)) return null;
      return after.tr.step(new GeometryStep(old.map(geometry), updated.map(geometry))).setMeta("comments-recorded", true);
    },
    props: {
      decorations(state) {
        return DecorationSet.create(state.doc, commentAnnotations(state).filter((item) => Number.isInteger(item.from) && item.from < item.to && item.to <= state.doc.content.size).map((item) => Decoration.inline(item.from, item.to, { "class": "author-comment" + (item.state === "needs_review" ? " author-comment-pending" : ""), "data-comment-id": item.id })));
      },
      handleDOMEvents: { click(_view, event) {
        const element = event.target?.closest?.("[data-comment-id]");
        if (!element) return false;
        event.preventDefault();
        options.onClick?.(element.dataset.commentId, event);
        return true;
      } }
    },
    view() {
      return { update(view, previous2) {
        const current = key.getState(view.state), old = key.getState(previous2);
        if (current.items !== old.items && !current.silent) options.onChange?.(current.items);
      } };
    }
  });
}
function createCommentEditorState(doc3, initial = []) {
  return EditorState.create({ doc: doc3, plugins: [history(), createCommentPlugin({ initial })] });
}

// src/rich-engine.js
function createRichEditor(host, options = {}) {
  let baseline = loadDocument(options.source ?? "", options.content_format ?? "plain");
  let sourceRef = options.source_ref || null, cachedDoc = null, cachedBaseline = null, cachedSnapshot = null;
  const snapshot = () => {
    if (cachedDoc !== view.state.doc || cachedBaseline !== baseline) {
      cachedDoc = view.state.doc;
      cachedBaseline = baseline;
      cachedSnapshot = serializeDocument(cachedDoc, baseline);
    }
    return cachedSnapshot;
  };
  let readOnly = Boolean(options.readOnly);
  const guard = (command) => (state, dispatch, editor) => !readOnly && command(state, dispatch, editor);
  const safeBase = Object.fromEntries(Object.entries(baseKeymap).map(([key2, command]) => [key2, guard(command)]));
  const view = new EditorView(host, {
    state: EditorState.create({ doc: baseline.doc, plugins: [history(), createCommentPlugin({ onClick: (...args) => options.onCommentClick?.(...args), onChange: (items) => options.onCommentsChange?.(items) }), keymap({ "Mod-z": guard(undo), "Mod-y": guard(redo), "Shift-Mod-z": guard(redo), "Mod-b": guard(toggleMark(schema.marks.strong)), "Mod-i": guard(toggleMark(schema.marks.em)) }), keymap(safeBase)] }),
    editable: () => !readOnly,
    dispatchTransaction(transaction) {
      const before = view.state;
      view.updateState(before.apply(transaction));
      options.onTransaction?.(transaction, before, view.state);
      if (transaction.docChanged) options.onInput?.();
    },
    // Paste is text-only; never import untrusted HTML, styles or remote images.
    handlePaste(_view, event) {
      if (readOnly) return true;
      const text4 = event.clipboardData?.getData("text/plain");
      if (text4 === void 0) return false;
      const parsed = loadDocument(text4, "plain").doc;
      const nodes = [];
      parsed.forEach((node2) => nodes.push(schema.nodes.paragraph.create(null, node2.content)));
      const fragment = schema.nodes.doc.create(null, nodes).content;
      view.dispatch(view.state.tr.replaceSelection(new Slice(fragment, 1, 1)).scrollIntoView());
      return true;
    }
  });
  return {
    view,
    snapshot,
    markSaved(snapshot2) {
      const loaded = loadDocument(snapshot2.source, snapshot2.content_format);
      loaded.doc = view.state.doc;
      loaded.sourceMap.doc = view.state.doc;
      loaded.blocks = loaded.blocks.map((block, index2) => ({ ...block, node: view.state.doc.child(index2), id: view.state.doc.child(index2).attrs.sourceId }));
      baseline = loaded;
      sourceRef = snapshot2.source_ref || sourceRef;
    },
    selection: () => ({ from: view.state.selection.from, to: view.state.selection.to }),
    canComment() {
      const range = view.state.selection;
      if (readOnly || range.empty) return { allowed: false, reason: "select" };
      if (commentAnnotations(view.state).some((item) => Number.isInteger(item.from) && range.from < item.to && range.to > item.from)) return { allowed: false, reason: "overlap" };
      try {
        toSourceRange(range, snapshot().sourceMap);
        return { allowed: true };
      } catch {
        return { allowed: false, reason: "unsupported" };
      }
    },
    prepareComment(id) {
      const range = { from: view.state.selection.from, to: view.state.selection.to };
      if (!this.canComment().allowed) throw new Error("Comment selection is unavailable");
      const current = snapshot(), anchor = toSourceRange(range, current.sourceMap);
      const saved = sourceRef?.sha256 && current.source === baseline.source && current.content_format === baseline.content_format;
      return { id, ...range, state: "valid", reason: null, origin: {
        doc: view.state.doc,
        ...range,
        anchor,
        ref: saved ? { version_id: sourceRef.id, sha256: sourceRef.sha256, content_format: sourceRef.content_format } : null,
        source: saved ? null : { text: current.source, content_format: current.content_format }
      } };
    },
    upsertComment(candidate) {
      if (readOnly || !candidate.origin?.doc?.eq(view.state.doc)) throw new Error("Comment source changed");
      const items = commentAnnotations(view.state).filter((item) => item.id !== candidate.id);
      view.dispatch(replaceCommentAnnotations(view.state.tr, [...items, candidate]));
    },
    removeComment(id) {
      if (!readOnly) view.dispatch(replaceCommentAnnotations(view.state.tr, commentAnnotations(view.state).filter((item) => item.id !== id)));
    },
    captureComments() {
      const current = snapshot();
      return commentAnnotations(view.state).map((item) => ({ id: item.id, anchor: item.state === "valid" ? { ...toSourceRange(item, current.sourceMap), state: "valid", reason: null, origin: null } : {
        ...item.origin.anchor,
        state: "needs_review",
        reason: item.reason || "modified",
        origin: item.origin.ref || null,
        ...item.origin.source ? { origin_source: item.origin.source } : {}
      } }));
    },
    setComments(notes, { mismatch = false } = {}) {
      const current = snapshot();
      const bindings = new Map(commentAnnotations(view.state).map((item) => [item.id, item.binding]));
      const items = (notes?.comments || []).map((comment) => {
        const anchor = comment.anchor;
        const ref = { version_id: notes.source_version_id, sha256: notes.source_sha256, content_format: notes.content_format };
        if (anchor.state === "needs_review" || mismatch) return { id: comment.id, binding: bindings.get(comment.id), from: null, to: null, state: "needs_review", reason: anchor.reason || "source_changed", origin: { anchor: { ...anchor, origin: null }, ref: anchor.origin || ref, source: null, doc: null } };
        const range = toDocumentRange(anchor, current.sourceMap);
        return { id: comment.id, binding: bindings.get(comment.id), ...range, state: "valid", reason: null, origin: { doc: view.state.doc, ...range, anchor: { ...anchor, origin: null }, ref, source: null } };
      });
      view.dispatch(replaceCommentAnnotations(view.state.tr, items, { silent: true }));
    },
    commentQuote(id) {
      const item = commentAnnotations(view.state).find((item2) => item2.id === id);
      return item?.origin.anchor.display_quote || "";
    },
    selectComment(id) {
      const item = commentAnnotations(view.state).find((item2) => item2.id === id);
      if (Number.isInteger(item?.from)) view.dispatch(view.state.tr.setSelection(TextSelection.create(view.state.doc, item.from, item.to)));
    },
    readOnly(value) {
      readOnly = Boolean(value);
      view.setProps({ editable: () => !readOnly });
    },
    isReadOnly: () => readOnly,
    canUndo: () => !readOnly && undo(view.state),
    canRedo: () => !readOnly && redo(view.state),
    canToggle: (mark) => !readOnly && toggleMark(schema.marks[mark])(view.state),
    toggle(mark) {
      if (readOnly) return false;
      return toggleMark(schema.marks[mark])(view.state, view.dispatch, view);
    },
    undo() {
      return !readOnly && undo(view.state, view.dispatch);
    },
    redo() {
      return !readOnly && redo(view.state, view.dispatch);
    },
    focus: () => view.focus(),
    destroy: () => view.destroy()
  };
}
export {
  SourceMappingError,
  codepointOffset,
  commentAnnotations,
  createCommentEditorState,
  createRichEditor,
  loadDocument,
  redo as redoTransaction,
  replaceCommentAnnotations,
  schema,
  serializeDocument,
  toDocumentRange,
  toSourceRange,
  undo as undoTransaction,
  utf16Offset
};
