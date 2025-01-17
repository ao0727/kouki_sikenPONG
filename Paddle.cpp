#include "Paddle.h"
#include "DxLib.h"
#include "Ball.h"

Paddle::Paddle(int startX, int startY) : x(startX), y(startY), width(10), height(60), speed(5) {}


void Paddle::Update(int upKey, int downKey) {
    if (CheckHitKey(upKey) && y > 0) {
        y -= speed;
    }
    if (CheckHitKey(downKey) && y + height < 480) {
        y += speed;
    }
}

//ボールのY座標に応じてCPUのパドルを移動させる
void Paddle::AIControl(const Ball& ball) {
    if (ball.GetY() < y && y > 0) {
        y -= speed;
    }
    if (ball.GetY() > y + height && y + height < 480) {
        y += speed;
    }
}

void Paddle::Draw() const {
    DrawBox(x, y, x + width, y + height, GetColor(255, 255, 255), TRUE);
}

int Paddle::GetX() const { return x; }
int Paddle::GetY() const { return y; }
int Paddle::GetWidth() const { return width; }
int Paddle::GetHeight() const { return height; }
