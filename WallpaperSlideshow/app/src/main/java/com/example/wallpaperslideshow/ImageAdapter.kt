package com.example.wallpaperslideshow

import android.graphics.Bitmap
import android.util.LruCache
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.lifecycle.LifecycleCoroutineScope
import androidx.recyclerview.widget.RecyclerView
import com.example.wallpaperslideshow.databinding.ItemImageBinding
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.Collections

/** 選択中の画像をグリッド表示するアダプター(並び替え・削除対応) */
class ImageAdapter(
    private val store: ImageStore,
    private val scope: LifecycleCoroutineScope,
    private val onRemove: (String) -> Unit
) : RecyclerView.Adapter<ImageAdapter.Holder>() {

    private val items = mutableListOf<String>()
    private var currentImage: String? = null

    private val cache = object : LruCache<String, Bitmap>(
        (Runtime.getRuntime().maxMemory() / 8 / 1024).toInt()
    ) {
        override fun sizeOf(key: String, value: Bitmap) = value.byteCount / 1024
    }

    val currentItems: List<String> get() = items.toList()

    fun submit(newItems: List<String>) {
        items.clear()
        items.addAll(newItems)
        notifyDataSetChanged()
    }

    fun setCurrent(name: String?) {
        if (name == currentImage) return
        currentImage = name
        notifyItemRangeChanged(0, items.size)
    }

    fun move(from: Int, to: Int) {
        if (from < to) {
            for (i in from until to) Collections.swap(items, i, i + 1)
        } else {
            for (i in from downTo to + 1) Collections.swap(items, i, i - 1)
        }
        notifyItemMoved(from, to)
    }

    /** 並び替え後の番号表示を更新する */
    fun refreshPositions() = notifyItemRangeChanged(0, items.size)

    override fun getItemCount() = items.size

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): Holder {
        val binding = ItemImageBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return Holder(binding)
    }

    override fun onBindViewHolder(holder: Holder, position: Int) {
        val name = items[position]
        val b = holder.binding
        b.position.text = (position + 1).toString()
        b.currentBadge.visibility = if (name == currentImage) View.VISIBLE else View.GONE
        b.removeButton.setOnClickListener {
            val pos = holder.bindingAdapterPosition
            if (pos != RecyclerView.NO_POSITION) onRemove(items[pos])
        }

        b.thumbnail.tag = name
        val cached = cache.get(name)
        if (cached != null) {
            b.thumbnail.setImageBitmap(cached)
            return
        }
        b.thumbnail.setImageDrawable(null)
        scope.launch {
            val bitmap = withContext(Dispatchers.IO) {
                runCatching { BitmapLoader.loadThumbnail(store.fileOf(name), THUMB_SIZE) }.getOrNull()
            } ?: return@launch
            cache.put(name, bitmap)
            // 読み込み中に別の画像へ再利用されていたら反映しない
            if (b.thumbnail.tag == name) b.thumbnail.setImageBitmap(bitmap)
        }
    }

    class Holder(val binding: ItemImageBinding) : RecyclerView.ViewHolder(binding.root)

    companion object {
        private const val THUMB_SIZE = 320
    }
}
