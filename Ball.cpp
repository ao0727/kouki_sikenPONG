#include "Ball.h"
#include "DxLib.h"

//ボールの挙動やスコア管理をする

Ball::Ball(int startX, int startY, Score& scoreRef)
    : x(startX), y(startY), speedX(5), speedY(5), size(10), score(scoreRef) {}

void Ball::Update() {
    // ボールの位置更新
    x += speedX;
    y += speedY;

    // 画面端での跳ね返り
    if (y <= 0 || y >= 480 - size) {
        speedY = -speedY; // 反射
    }

    // 左右の壁に当たったら得点を加算
    if (x <= 0) {
        score.AddCpuScore();  // 左壁に当たったらCPUの得点
        Reset(300, 240);      // ボールをリセット
    }
    if (x >= 640 - size) {
        score.AddPlayerScore(); // 右壁に当たったらプレイヤーの得点
        Reset(300, 240);        // ボールをリセット
    }
}

void Ball::Draw() const {
    DrawCircle(x, y, size, GetColor(255, 255, 255), TRUE); // ボールを描画
}

void Ball::CheckCollision(Paddle& player, Paddle& cpu) {
    // プレイヤーとCPUパドルとの衝突判定
    if (x - size < player.GetX() + player.GetWidth() &&
        x + size > player.GetX() &&
        y > player.GetY() &&
        y < player.GetY() + player.GetHeight()) {
        speedX = -speedX; // 水平方向の速度反転
    }

    // CPUのパドルとボールの衝突
    if (x + size > cpu.GetX() &&
        x - size < cpu.GetX() + cpu.GetWidth() &&
        y > cpu.GetY() &&
        y < cpu.GetY() + cpu.GetHeight()) {
        speedX = -speedX; // 水平方向の速度反転
    }
}

void Ball::Reset(int startX, int startY) {
    x = startX;
    y = startY;
    speedX = 5;
    speedY = 5;
}
