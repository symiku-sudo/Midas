package com.midas.client.ui.components

import android.text.method.LinkMovementMethod
import android.text.util.Linkify
import android.widget.TextView
import androidx.core.text.util.LinkifyCompat
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import io.noties.markwon.Markwon

@Composable
fun MarkdownText(
    markdown: String,
    textColor: Color = Color.Unspecified,
    linkColor: Color = Color.Unspecified,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val markwon = remember(context) { Markwon.create(context) }
    val resolvedTextColor = if (textColor == Color.Unspecified) {
        MaterialTheme.colorScheme.onSurface
    } else {
        textColor
    }
    val resolvedLinkColor = if (linkColor == Color.Unspecified) {
        MaterialTheme.colorScheme.primary
    } else {
        linkColor
    }

    AndroidView(
        modifier = modifier,
        factory = { viewContext ->
            TextView(viewContext).apply {
                setTextIsSelectable(false)
                linksClickable = true
                movementMethod = LinkMovementMethod.getInstance()
            }
        },
        update = { view ->
            markwon.setMarkdown(view, markdown)
            LinkifyCompat.addLinks(view, Linkify.WEB_URLS)
            view.setTextColor(resolvedTextColor.toArgb())
            view.setLinkTextColor(resolvedLinkColor.toArgb())
        },
    )
}
